# SPDX-License-Identifier: GPL-3.0-or-later
"""Synchronous access to the local versioned JSON API and CLI arbitration."""

import errno
import http.client
import io
import json
import math
import os
import socket
import time
from contextlib import closing, contextmanager
from typing import Any, Dict, Mapping, Optional

from .ownership import DeviceOwnership, OwnershipError
from .store import SlotAssignment


DEFAULT_SOCKET = "/run/ryuo-screen/control.sock"
API_PREFIX = "/api/v1"
_ABSENT_ERRORS = (errno.ENOENT, errno.ECONNREFUSED)
_WIDGET_MEASUREMENTS = {
    "CPU Load": "cpu.load",
    "CPU Usage": "cpu.usage",
    "CPU Temperature": "cpu.temperature",
    "CPU Speed Average": "cpu.frequency",
    "CPU Voltage": "cpu.voltage",
    "GPU Load": "gpu.load",
    "GPU Usage": "gpu.usage",
    "GPU Temperature": "gpu.temperature",
    "GPU Speed": "gpu.clock.core",
    "GPU Frequency": "gpu.clock.core",
    "GPU Power": "gpu.power",
    "GPU Voltage": "gpu.voltage",
    "Memory Utilization": "memory.load",
    "Memory Frequency": "memory.frequency",
    "Hard Disk Temperature": "disk.temperature",
    "Motherboard Temperature": "motherboard.temperature",
    "Date&Time": "time.datetime",
    "Date": "time.date",
    "Time": "time.clock",
}


class ApiError(RuntimeError):
    """The service could not complete a request."""

    def __init__(
        self, message: str, status: Optional[int] = None,
        document: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.document = document


class ServiceUnavailable(ApiError):
    """No listener accepted the connection."""


class _DeadlineReader(io.RawIOBase):
    """Keep an absolute deadline even if a listener sends bytes slowly."""

    def __init__(self, stream: socket.socket, deadline: float) -> None:
        self.stream = stream
        self.deadline = deadline

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        _set_remaining_timeout(self.stream, self.deadline)
        return self.stream.recv_into(buffer)

    def makefile(self, _mode: str) -> io.BufferedReader:
        return io.BufferedReader(self)


def _set_remaining_timeout(stream: socket.socket, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Ryuo service request timed out")
    stream.settimeout(remaining)


def _connect(path: str, deadline: float) -> socket.socket:
    if not hasattr(socket, "AF_UNIX"):
        raise ServiceUnavailable("Unix sockets are unavailable on this platform")
    try:
        stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    except OSError as exc:
        if exc.errno in (errno.EAFNOSUPPORT, errno.EPROTONOSUPPORT):
            raise ServiceUnavailable("Unix sockets are unavailable on this platform") from exc
        raise ApiError("cannot create a Unix socket: {}".format(exc)) from exc
    try:
        _set_remaining_timeout(stream, deadline)
        stream.connect(path)
    except OSError as exc:
        stream.close()
        if exc.errno in _ABSENT_ERRORS:
            raise ServiceUnavailable("no Ryuo service listening at {}".format(path)) from exc
        raise ApiError("cannot connect to Ryuo service at {}: {}".format(path, exc)) from exc
    return stream


def _reject_nonfinite(literal: str) -> None:
    raise ValueError("{} is not valid JSON".format(literal))


class UnixApiClient:
    """Speak regular HTTP over a filesystem Unix-domain socket."""

    def __init__(
        self, socket_path=DEFAULT_SOCKET, *, timeout: float = 25.0,
        max_response_bytes: int = 1024 * 1024,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0 or max_response_bytes < 1:
            raise ValueError("timeout and maximum response size must be positive")
        self.socket_path = os.fspath(socket_path)
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes

    def request(
        self, method: str, path: str, body: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not path.startswith(API_PREFIX + "/"):
            raise ValueError("request path must start with /api/v1/")
        deadline = time.monotonic() + self.timeout
        stream = _connect(self.socket_path, deadline)
        with closing(stream):
            try:
                headers = {"Accept": "application/json", "Connection": "close"}
                payload = None
                if body is not None:
                    payload = json.dumps(
                        dict(body), ensure_ascii=False, allow_nan=False
                    ).encode("utf-8")
                    headers["Content-Type"] = "application/json"
                _set_remaining_timeout(stream, deadline)
                connection = http.client.HTTPConnection("localhost")
                connection.auto_open = 0  # Only the connected Unix socket is permitted.
                connection.sock = stream
                connection.request(method, path, body=payload, headers=headers)
                with closing(http.client.HTTPResponse(
                    _DeadlineReader(stream, deadline), method=method
                )) as response:
                    response.begin()
                    return self._read_json(response)
            except (OSError, http.client.HTTPException) as exc:
                raise ApiError("Ryuo service HTTP request failed: {}".format(exc)) from exc

    def _read_json(self, response: http.client.HTTPResponse) -> Dict[str, Any]:
        limit = self.max_response_bytes
        if response.length is not None and response.length > limit:
            raise ApiError("Ryuo service response exceeds the size limit", response.status)
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ApiError("Ryuo service response exceeds the size limit", response.status)
        if response.length:
            raise ApiError("Ryuo service returned a truncated response", response.status)
        try:
            if response.headers.get_content_type() != "application/json":
                raise ValueError("expected application/json")
            document = json.loads(raw.decode("utf-8"), parse_constant=_reject_nonfinite)
        except (ValueError, RecursionError) as exc:
            raise ApiError(
                "Ryuo service returned invalid JSON (HTTP {})".format(response.status),
                response.status,
            ) from exc
        if not isinstance(document, dict):
            raise ApiError("Ryuo service JSON response must be an object", response.status)
        if not 200 <= response.status < 300:
            detail = document.get("message") or document.get("error") or "request failed"
            raise ApiError(
                "Ryuo service HTTP {}: {}".format(response.status, detail),
                response.status, document,
            )
        return document


def add_service_options(parser) -> None:
    parser.add_argument(
        "--direct", action="store_true",
        help="use HID directly after stopping the service and other direct sessions "
             "(cross-process ownership checks on Linux)",
    )
    parser.add_argument("--socket", default=DEFAULT_SOCKET,
                        help="Unix socket for the local service (default: %(default)s)")


@contextmanager
def direct_device(socket_path, open_handle, *args):
    """Claim HID before probing or opening, and hold it until the handle closes."""
    with DeviceOwnership():
        try:
            stream = _connect(socket_path, time.monotonic() + 0.25)
        except ServiceUnavailable:
            pass
        else:
            stream.close()
            raise OwnershipError(
                "the Ryuo service is active at {}. Use a service command, "
                "or stop the service before opening HID.".format(socket_path)
            )
        handle = open_handle(*args)
        try:
            yield handle
        finally:
            handle.close()


def patch_state(client: UnixApiClient, state: Dict[str, Any], resource: str, **changes):
    revision = state.get("revision")
    if type(revision) is not int or revision < 0:
        raise ApiError("Ryuo service returned an invalid state revision")
    return client.request("PATCH", API_PREFIX + resource, dict(changes, revision=revision))


def print_state_result(result: Dict[str, Any]) -> None:
    print(json.dumps(result), flush=True)
    if result.get("error"):
        raise ApiError(str(result["error"]))
    if result.get("saved") is not True or not (
        result.get("queued") is True or result.get("applied") is True
    ):
        raise ApiError("Ryuo service did not accept the device update")


def slots_for_items(items, client: UnixApiClient):
    """Preserve firmware widget names and map fan labels to service readings."""
    fans = None
    slots = []
    for widget in items:
        measurement = _WIDGET_MEASUREMENTS.get(widget)
        label = None
        if widget.startswith("Fan Speed "):
            if fans is None:
                fans = client.request("GET", API_PREFIX + "/sensors").get("sensors", [])
            label = widget[len("Fan Speed "):]
            readings = {
                sensor["measurementId"] for sensor in fans
                if sensor.get("label") == label and sensor.get("unit") == "RPM"
                and str(sensor.get("measurementId", "")).startswith("fan.")
            }
            if len(readings) == 1:
                measurement = readings.pop()
        if widget and measurement is None:
            raise ApiError(
                "item {!r} has no unambiguous service equivalent. "
                "Stop the service to use this item in direct mode.".format(widget)
            )
        slots.append(SlotAssignment(bool(widget), measurement or "", widget, label).to_dict())
    return slots
