# SPDX-License-Identifier: GPL-3.0-or-later
"""Serialized HID ownership, incremental screen application and recovery."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

import ryuo_hid
import ryuo_proto as proto

from .models import CommandResult, SensorDescriptor, TelemetrySnapshot
from .store import ScreenState


PRIORITY_SHUTDOWN = 0
PRIORITY_KEEPALIVE = 10
PRIORITY_STATE = 30
PRIORITY_UI = 50
PRIORITY_ANIMATION = 100
MAX_SEQUENCE = 2_147_483_647
_FAN_ALIAS_OVERFLOW = "fan alias frame overflow"


def _boottime() -> float:
    """A suspend-aware monotonic clock where the platform exposes one."""
    clock_id = getattr(time, "CLOCK_BOOTTIME", None)
    if clock_id is not None:
        return time.clock_gettime(clock_id)
    return time.monotonic()


class DeviceTransport(Protocol):
    """The worker's narrow transport boundary; every method runs on its thread."""

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def transact(
        self, method: str, resource: str, payload: Optional[Mapping[str, Any]],
        *, seq: int, timeout: float,
    ) -> Optional[str]:
        ...

    def drain(self, limit: int = 32) -> int:
        ...


class HidTransport:
    """hidapi transport which re-enumerates the stable product on every open."""

    def __init__(
        self, hid_module=None, *, vid: Optional[int] = None, pid: int = proto.PID,
        interface: int = proto.INTERFACE, index: Optional[int] = None,
    ) -> None:
        if hid_module is None:
            import hid as hid_module  # type: ignore
        self._hid = hid_module
        self._vid = vid
        self._pid = pid
        self._interface = interface
        self._index = index
        self._handle = None

    def open(self) -> None:
        self.close()
        devices = proto.find_devices(self._hid, self._vid, self._pid)
        if not devices:
            raise OSError("Ryuo IV HID device is not present")
        if self._index is not None:
            try:
                selected = devices[self._index]
            except IndexError as exc:
                raise OSError("HID device index is no longer present") from exc
        else:
            selected = next(
                (item for item in devices
                 if item.get("interface_number") == self._interface),
                devices[0],
            )
        handle = self._hid.device()
        handle.open_path(selected["path"])
        handle.set_nonblocking(1)
        self._handle = handle

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.close()

    def transact(
        self, method: str, resource: str, payload: Optional[Mapping[str, Any]],
        *, seq: int, timeout: float,
    ) -> Optional[str]:
        if self._handle is None:
            raise OSError("HID device is not open")
        return ryuo_hid.transact(
            self._handle, method, resource, dict(payload) if payload is not None else None,
            seq=seq, timeout=timeout,
        )

    def drain(self, limit: int = 32) -> int:
        if self._handle is None:
            return 0
        return ryuo_hid.drain(self._handle, max_reports=limit)


@dataclass(frozen=True)
class DeviceCommand:
    method: str
    resource: str
    payload: Optional[Mapping[str, Any]] = None
    priority: int = PRIORITY_UI
    coalesce_key: Optional[str] = None
    expect_reply: bool = False
    state: Optional[ScreenState] = None
    saved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.method, str) or not self.method:
            raise TypeError("command method must be a non-empty string")
        if not isinstance(self.resource, str) or not self.resource:
            raise TypeError("command resource must be a non-empty string")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("command priority must be an integer")
        if self.coalesce_key is not None and not isinstance(self.coalesce_key, str):
            raise TypeError("coalesce_key must be a string")
        if self.state is not None and not isinstance(self.state, ScreenState):
            raise TypeError("command state must be a ScreenState")
        if self.payload is not None:
            if not isinstance(self.payload, Mapping):
                raise TypeError("command payload must be a mapping")
            object.__setattr__(self, "payload", copy.deepcopy(dict(self.payload)))

    @classmethod
    def for_state(cls, state: ScreenState) -> "DeviceCommand":
        if not isinstance(state, ScreenState):
            raise TypeError("state must be a ScreenState")
        return cls(
            proto.POST,
            proto.RES_CONFIG,
            proto.config_payload_from_state(state),
            priority=PRIORITY_STATE,
            coalesce_key="screen-state",
            state=state,
            saved=True,
        )

    def validated(self, seq: int = 1) -> bytes:
        """Build the frame now so an oversized command never reaches HID."""
        return proto.request(
            self.method, self.resource,
            dict(self.payload) if self.payload is not None else None,
            seq=seq,
        )


@dataclass(frozen=True)
class ApplyPlan:
    commands: Tuple[DeviceCommand, ...] = ()
    full_config: bool = False
    requires_settle: bool = False


def plan_state_change(old: ScreenState, new: ScreenState) -> ApplyPlan:
    """Choose the least disruptive protocol operations for a state change."""
    if not isinstance(old, ScreenState) or not isinstance(new, ScreenState):
        raise TypeError("old and new must be ScreenState values")
    full_fields = ("screen_mode", "media", "playback_modes")
    if any(getattr(old, name) != getattr(new, name) for name in full_fields):
        command = DeviceCommand.for_state(new)
        command.validated(seq=MAX_SEQUENCE)
        return ApplyPlan((command,), full_config=True, requires_settle=True)

    commands: List[DeviceCommand] = []
    if old.brightness != new.brightness:
        commands.append(DeviceCommand(
            proto.POST, proto.RES_BRIGHTNESS, {"value": new.brightness},
            priority=PRIORITY_STATE, coalesce_key="brightness", saved=True,
        ))
    if old.temperature_unit != new.temperature_unit:
        commands.append(DeviceCommand(
            proto.POST, proto.RES_TEMPERATURE, {"value": new.temperature_unit},
            priority=PRIORITY_STATE, coalesce_key="temperature", saved=True,
        ))
    visual_fields = (
        "slots", "title_colors", "content_colors", "opacity",
        "rgb_mode", "rgb_target", "thermal_source",
    )
    if any(getattr(old, name) != getattr(new, name) for name in visual_fields):
        commands.append(DeviceCommand(
            proto.POST, proto.RES_PRESET, proto.preset_payload_from_state(new),
            priority=PRIORITY_STATE, coalesce_key="preset", saved=True,
        ))
    for command in commands:
        command.validated(seq=MAX_SEQUENCE)
    return ApplyPlan(tuple(commands), full_config=False)


class CommandTicket:
    """A bounded completion cell; waiting never runs on the device thread."""

    def __init__(self, *, saved: bool = False) -> None:
        self._event = threading.Event()
        self._result: Optional[CommandResult] = None
        self._saved = saved

    @property
    def done(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: Optional[float] = None) -> CommandResult:
        if not self._event.wait(timeout):
            return CommandResult(saved=self._saved, queued=True, error="timeout")
        assert self._result is not None
        return self._result

    def result(self, timeout: Optional[float] = None) -> CommandResult:
        """``Future``-style spelling used by non-device callers."""
        return self.wait(timeout)

    def snapshot(self) -> CommandResult:
        """Return immediate truthful flags without blocking the worker."""
        if self._result is not None:
            return self._result
        return CommandResult(saved=self._saved, queued=True)

    def _complete(self, result: CommandResult) -> None:
        if self._event.is_set():
            return
        self._result = result
        self._event.set()


@dataclass(frozen=True)
class DeviceStatus:
    phase: str = "stopped"
    connected: bool = False
    sequence: int = 0
    queue_depth: int = 0
    reconnect_count: int = 0
    recovery_count: int = 0
    last_ack: Optional[int] = None
    heartbeat_age: Optional[float] = None
    last_error: Optional[str] = None
    descriptor: Mapping[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    firmware: Optional[str] = None
    uptime: float = 0.0


@dataclass(frozen=True)
class LatestTelemetry:
    """Defensive latest structured sample captured by the HID owner thread."""

    snapshot: Optional[TelemetrySnapshot] = None
    catalog: Tuple[SensorDescriptor, ...] = ()
    error: Optional[str] = "telemetry has not been sampled"

    def __post_init__(self) -> None:
        if self.snapshot is not None and not isinstance(self.snapshot, TelemetrySnapshot):
            raise TypeError("snapshot must be a TelemetrySnapshot")
        object.__setattr__(self, "catalog", tuple(self.catalog))
        if any(not isinstance(item, SensorDescriptor) for item in self.catalog):
            raise TypeError("catalog entries must be SensorDescriptor values")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("telemetry error must be a string")


@dataclass
class _Queued:
    order: int
    command: DeviceCommand
    ticket: CommandTicket


class DeviceWorker:
    """One thread owns open/write/read/close for the lifetime of the service."""

    def __init__(
        self,
        transport: DeviceTransport,
        telemetry,
        state: Optional[ScreenState] = None,
        *,
        keepalive_interval: float = 1.0,
        settle_seconds: float = 1.6,
        reconnect_backoff: Sequence[float] = (0.25, 0.5, 1.0, 2.0, 5.0),
        max_rate: float = 8.0,
        queue_size: int = 64,
        clock: Callable[[], float] = _boottime,
        resume_gap_seconds: float = 5.0,
    ) -> None:
        if keepalive_interval <= 0 or settle_seconds < 0 or max_rate <= 0:
            raise ValueError("worker timing values are invalid")
        if queue_size < 1 or resume_gap_seconds <= 0:
            raise ValueError("queue_size must be positive")
        if not reconnect_backoff or any(value < 0 for value in reconnect_backoff):
            raise ValueError("reconnect_backoff must contain non-negative delays")
        self._transport = transport
        self._telemetry = telemetry
        self._desired_state = state or ScreenState()
        self._applied_state = self._desired_state
        self._keepalive_interval = float(keepalive_interval)
        self._settle_seconds = float(settle_seconds)
        self._backoff = tuple(float(value) for value in reconnect_backoff)
        self._min_send_gap = 1.0 / float(max_rate)
        self._queue_size = queue_size
        self._clock = clock
        self._resume_gap_seconds = float(resume_gap_seconds)

        self._condition = threading.Condition()
        self._pending: List[_Queued] = []
        self._order = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        self._resume_requested = False
        self._phase = "stopped"
        self._connected = False
        self._sequence = 1
        self._last_ack: Optional[int] = None
        self._last_heartbeat: Optional[float] = None
        self._last_send: Optional[float] = None
        self._last_error: Optional[str] = None
        self._descriptor: Dict[str, Any] = {}
        self._model: Optional[str] = None
        self._firmware: Optional[str] = None
        self._reconnect_count = 0
        self._recovery_count = 0
        self._ever_connected = False
        self._had_failure = False
        self._started_at: Optional[float] = None
        self._last_safe = proto.pc_info(timestamp_ms=0)
        self._latest_telemetry = LatestTelemetry()
        self._next_keepalive: Optional[float] = None
        self._last_loop_clock: Optional[float] = None
        self._session_active = False
        self._last_dynamic_preset: Optional[Mapping[str, Any]] = None

    def start(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop = False
            self._phase = "disconnected"
            self._started_at = self._clock()
            self._thread = threading.Thread(
                target=self._run, name="ryuo-device", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        with self._condition:
            thread = self._thread
            if thread is None:
                return
            self._stop = True
            self._condition.notify_all()
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError("device worker did not stop")
        with self._condition:
            self._thread = None

    def notify_resume(self) -> None:
        """Wake immediately after resume/udev and force a fresh handshake."""
        with self._condition:
            self._resume_requested = True
            self._condition.notify_all()

    def submit(self, command: DeviceCommand) -> CommandTicket:
        if not isinstance(command, DeviceCommand):
            raise TypeError("command must be a DeviceCommand")
        ticket = CommandTicket(saved=command.saved)
        try:
            command.validated(seq=MAX_SEQUENCE)
        except (TypeError, ValueError) as exc:
            ticket._complete(CommandResult(
                saved=command.saved, queued=False, error=str(exc)
            ))
            return ticket

        with self._condition:
            if self._stop or self._thread is None:
                ticket._complete(CommandResult(
                    saved=command.saved, queued=False, error="worker is not running"
                ))
                return ticket
            if command.coalesce_key:
                for index, queued in enumerate(self._pending):
                    if queued.command.coalesce_key == command.coalesce_key:
                        queued.ticket._complete(CommandResult(
                            saved=queued.command.saved, queued=True, error="superseded"
                        ))
                        self._order += 1
                        self._pending[index] = _Queued(self._order, command, ticket)
                        if command.state is not None:
                            self._desired_state = command.state
                        self._condition.notify_all()
                        return ticket
            if len(self._pending) >= self._queue_size:
                ticket._complete(CommandResult(
                    saved=command.saved, queued=False, error="device queue is full"
                ))
                return ticket
            self._order += 1
            self._pending.append(_Queued(self._order, command, ticket))
            if command.state is not None:
                self._desired_state = command.state
            self._condition.notify_all()
        return ticket

    def status(self) -> DeviceStatus:
        with self._condition:
            now = self._clock()
            return DeviceStatus(
                phase=self._phase,
                connected=self._connected,
                sequence=self._sequence - 1,
                queue_depth=len(self._pending),
                reconnect_count=self._reconnect_count,
                recovery_count=self._recovery_count,
                last_ack=self._last_ack,
                heartbeat_age=(None if self._last_heartbeat is None
                               else max(0.0, now - self._last_heartbeat)),
                last_error=self._last_error,
                descriptor=copy.deepcopy(self._descriptor),
                model=self._model,
                firmware=self._firmware,
                uptime=(0.0 if self._started_at is None
                        else max(0.0, now - self._started_at)),
            )

    def latest_telemetry(self) -> LatestTelemetry:
        """Return a non-collecting copy safe for HTTP/event-loop consumers."""
        with self._condition:
            return copy.deepcopy(self._latest_telemetry)

    def _run(self) -> None:
        backoff_index = 0
        try:
            while not self._should_stop():
                if not self._connected:
                    try:
                        self._connect()
                    except Exception as exc:
                        if self._should_stop():
                            break
                        self._mark_disconnected(exc)
                        delay = self._backoff[min(backoff_index, len(self._backoff) - 1)]
                        backoff_index += 1
                        self._wait_backoff(delay)
                        continue
                    backoff_index = 0
                    if self._should_stop():
                        break

                now = self._clock()
                if (self._last_loop_clock is not None
                        and now - self._last_loop_clock >= self._resume_gap_seconds):
                    self._last_loop_clock = now
                    self._mark_disconnected(OSError("suspend/boottime gap detected"))
                    continue
                self._last_loop_clock = now

                with self._condition:
                    if self._resume_requested:
                        self._resume_requested = False
                        force_reconnect = True
                    else:
                        force_reconnect = False
                if force_reconnect:
                    self._mark_disconnected(OSError("resume/hotplug re-enumeration"))
                    continue

                try:
                    self._transport.drain(limit=32)
                    now = self._clock()
                    queued = self._peek()
                    if (self._next_keepalive is not None and now >= self._next_keepalive
                            and (queued is None
                                 or queued.command.priority >= PRIORITY_KEEPALIVE)):
                        self._send_keepalive()
                        continue
                    queued = self._pop()
                    if queued is not None:
                        self._process(queued)
                        continue
                    delay = (self._keepalive_interval if self._next_keepalive is None
                             else max(0.0, self._next_keepalive - now))
                    self._wait(min(delay, 0.25))
                except OSError as exc:
                    if self._should_stop():
                        break
                    self._mark_disconnected(exc)
                except Exception as exc:
                    with self._condition:
                        self._last_error = "worker: {}".format(exc)
        finally:
            if self._session_active:
                try:
                    self._send(proto.POST, proto.RES_DISCONN, None, timeout=0.2,
                               bypass_rate=True)
                except Exception:
                    pass
            try:
                self._transport.close()
            except Exception:
                pass
            with self._condition:
                self._connected = False
                self._session_active = False
                self._phase = "stopped"
                for queued in self._pending:
                    queued.ticket._complete(CommandResult(
                        saved=queued.command.saved, queued=True,
                        error="worker stopped before apply",
                    ))
                self._pending.clear()
                self._condition.notify_all()

    def _connect(self) -> None:
        with self._condition:
            self._phase = "connecting"
            self._last_dynamic_preset = None
        self._transport.open()
        try:
            body = self._send(proto.POST, proto.RES_CONN, None, timeout=0.5,
                              bypass_rate=True)
            with self._condition:
                self._session_active = True
            descriptor = proto.reply_json(body)
            if not isinstance(descriptor, dict):
                descriptor = {}
            descriptor = proto.redact_conn(descriptor)
            with self._condition:
                self._descriptor = descriptor
                self._model = self._descriptor_value(
                    descriptor, ("model", "product", "productName", "name")
                )
                self._firmware = self._descriptor_value(
                    descriptor, ("firmware", "firmwareVersion", "fwVersion", "version")
                )
                self._phase = "configuring"
            configured_state = self._desired_state
            payload = proto.config_payload_from_state(configured_state)
            proto.request(proto.POST, proto.RES_CONFIG, payload, seq=self._sequence)
            self._send(proto.POST, proto.RES_CONFIG, payload, timeout=0.5)
            if self._settle_seconds and self._sleep(self._settle_seconds):
                return
            telemetry_ok = self._send_keepalive()
            with self._condition:
                self._connected = True
                self._phase = "healthy" if telemetry_ok else "degraded"
                if telemetry_ok:
                    self._last_error = None
                self._reconnect_count += 1
                if self._ever_connected or self._had_failure:
                    self._recovery_count += 1
                self._ever_connected = True
                self._had_failure = False
                self._applied_state = configured_state
                self._last_loop_clock = self._clock()
                remaining = []
                for queued in self._pending:
                    if queued.command.state == configured_state:
                        queued.ticket._complete(CommandResult(
                            saved=True, queued=True, applied=True,
                            acked=False,
                        ))
                    else:
                        remaining.append(queued)
                self._pending = remaining
                self._condition.notify_all()
        except Exception:
            if not self._should_stop():
                self._transport.close()
            raise

    @staticmethod
    def _descriptor_value(document: Mapping[str, Any], keys: Sequence[str]) -> Optional[str]:
        for key in keys:
            value = document.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _process(self, queued: _Queued) -> None:
        command = queued.command
        if command.state is not None:
            try:
                plan = plan_state_change(self._applied_state, command.state)
                acked = True
                for planned in plan.commands:
                    body = self._send(
                        planned.method, planned.resource, planned.payload,
                        timeout=0.3 if planned.expect_reply else 0,
                    )
                    acked = acked and body is not None
                if plan.requires_settle:
                    if self._settle_seconds and self._sleep(self._settle_seconds):
                        raise OSError("worker stopped while applying config")
                    self._send_keepalive()
            except ValueError as exc:
                queued.ticket._complete(CommandResult(
                    saved=True, queued=True, applied=False, error=str(exc)
                ))
                with self._condition:
                    self._last_error = "command: {}".format(exc)
                return
            except OSError:
                # Keep the latest state queued: reconnect's full config applies it.
                self._requeue_failed_state(queued)
                raise
            self._applied_state = command.state
            queued.ticket._complete(CommandResult(
                saved=True, queued=True, applied=True,
                acked=bool(plan.commands) and acked,
            ))
            return
        try:
            body = self._send(
                command.method, command.resource, command.payload,
                timeout=0.3 if command.expect_reply else 0,
            )
        except ValueError as exc:
            queued.ticket._complete(CommandResult(
                saved=command.saved, queued=True, applied=False, error=str(exc)
            ))
            with self._condition:
                self._last_error = "command: {}".format(exc)
            return
        except OSError as exc:
            queued.ticket._complete(CommandResult(
                saved=command.saved, queued=True, applied=False, error=str(exc)
            ))
            raise
        queued.ticket._complete(CommandResult(
            saved=command.saved, queued=True, applied=True,
            acked=body is not None,
        ))

    def _send_keepalive(self) -> bool:
        try:
            payload, telemetry_error = self._collect_telemetry()
            self._last_safe = payload
        except Exception as exc:
            payload = self._last_safe
            telemetry_error = "telemetry: {}".format(exc)
            with self._condition:
                self._latest_telemetry = LatestTelemetry(
                    self._latest_telemetry.snapshot,
                    self._latest_telemetry.catalog,
                    str(exc),
                )
        telemetry_ok = telemetry_error is None
        with self._condition:
            if self._connected:
                self._phase = "healthy" if telemetry_ok else "degraded"
            if telemetry_error is not None:
                self._last_error = telemetry_error
            elif self._connected and self._last_error and (
                self._last_error.startswith("telemetry:")
                or self._last_error == _FAN_ALIAS_OVERFLOW
            ):
                self._last_error = None
        self._send(proto.POST, proto.RES_ALL, payload, timeout=0)
        now = self._clock()
        dynamic = self._dynamic_preset_payload(now)
        if dynamic is not None and dynamic != self._last_dynamic_preset:
            self._send(proto.POST, proto.RES_PRESET, dynamic, timeout=0)
            self._last_dynamic_preset = copy.deepcopy(dynamic)
        elif dynamic is None:
            self._last_dynamic_preset = None
        with self._condition:
            self._last_heartbeat = now
            next_tick = ((self._next_keepalive or now) + self._keepalive_interval)
            self._next_keepalive = (now + self._keepalive_interval
                                    if next_tick < now else next_tick)
        return telemetry_ok

    def _dynamic_preset_payload(self, now: float) -> Optional[Mapping[str, Any]]:
        with self._condition:
            state = self._desired_state
            snapshot = self._latest_telemetry.snapshot
        if state.rgb_mode == "off":
            return None
        if state.rgb_mode == "hue":
            colour = proto.hsv_hex((float(now) % 10.0) / 10.0)
        else:
            if snapshot is None:
                return None
            reading = snapshot.measurements.get(state.thermal_source)
            if (
                reading is None or not reading.available
                or not isinstance(reading.value, (int, float))
                or isinstance(reading.value, bool)
            ):
                return None
            colour = proto.thermal_hex(
                float(reading.value), phase=bool(int(float(now)) % 2)
            )
        title = state.title_colors
        content = state.content_colors
        if state.rgb_target in ("title", "both"):
            title = tuple(colour for _ in title)
        if state.rgb_target in ("value", "both"):
            content = tuple(colour for _ in content)
        return proto.preset_payload_from_state(replace(
            state, title_colors=title, content_colors=content
        ))

    def _collect_telemetry(self) -> Tuple[Mapping[str, Any], Optional[str]]:
        warning = None
        if callable(self._telemetry):
            value = self._telemetry()
            with self._condition:
                self._latest_telemetry = LatestTelemetry(
                    error="structured telemetry is unavailable from callable source"
                )
        else:
            with self._condition:
                state = self._desired_state
            set_selectors = getattr(self._telemetry, "set_selectors", None)
            if callable(set_selectors):
                set_selectors(state.sensor_selectors)
            snapshot = self._telemetry.sample()
            slots = state.slots
            catalog = tuple(self._telemetry.catalog())
            aliases = {}
            for slot in slots:
                reading = snapshot.measurements.get(slot.measurement_id)
                if (
                    slot.enabled
                    and slot.label
                    and slot.widget == "Fan Speed " + slot.label
                    and slot.measurement_id.startswith("fan.")
                    and reading is not None
                    and reading.available
                    and reading.unit == "RPM"
                    and isinstance(reading.value, (int, float))
                    and not isinstance(reading.value, bool)
                ):
                    descriptor = next((item for item in catalog if (
                        item.measurement_id == slot.measurement_id
                        and item.ref == reading.ref and item.unit == "RPM"
                    )), None)
                    if descriptor is not None:
                        aliases[(slot.measurement_id, reading.ref)] = slot.label
            value = self._telemetry.to_pc_info(snapshot)
            if aliases:
                aliased = self._telemetry.to_pc_info(
                    snapshot, fan_aliases=aliases
                )
                try:
                    proto.request(
                        proto.POST, proto.RES_ALL, aliased, seq=MAX_SEQUENCE
                    )
                except ValueError:
                    # Telemetry magnitude can grow after state admission.
                    # Keep the original names and report the missing aliases.
                    warning = _FAN_ALIAS_OVERFLOW
                else:
                    value = aliased
            with self._condition:
                self._latest_telemetry = LatestTelemetry(snapshot, catalog, None)
        if not isinstance(value, Mapping):
            raise TypeError("telemetry source must return a mapping")
        # Oversized runtime samples are collection failures. _send_keepalive
        # then reuses the previously bounded safe payload instead of writing a
        # frame the firmware will drop and reconnecting forever.
        proto.request(proto.POST, proto.RES_ALL, value, seq=MAX_SEQUENCE)
        return dict(value), warning

    def _send(
        self, method: str, resource: str, payload: Optional[Mapping[str, Any]],
        *, timeout: float, bypass_rate: bool = False,
    ) -> Optional[str]:
        seq = self._sequence
        if seq > MAX_SEQUENCE:
            raise ValueError("device sequence counter exceeded supported range")
        proto.request(method, resource, dict(payload) if payload is not None else None, seq=seq)
        if not bypass_rate and self._last_send is not None:
            delay = self._min_send_gap - (self._clock() - self._last_send)
            if delay > 0 and self._sleep(delay):
                raise OSError("worker stopped before write")
        self._sequence += 1
        body = self._transport.transact(
            method, resource, payload, seq=seq, timeout=timeout
        )
        self._last_send = self._clock()
        ack = proto.reply_ack(body)
        if ack is not None:
            with self._condition:
                self._last_ack = ack
        return body

    def _mark_disconnected(self, exc: Exception) -> None:
        try:
            self._transport.close()
        except Exception:
            pass
        with self._condition:
            self._connected = False
            self._session_active = False
            self._phase = "disconnected"
            self._last_error = str(exc)
            self._had_failure = True
            self._next_keepalive = None
            self._last_loop_clock = None
            self._condition.notify_all()

    def _requeue_failed_state(self, queued: _Queued) -> None:
        """Retain an accepted saved state without ever exceeding queue_size."""
        with self._condition:
            newer = any(
                item.command.coalesce_key == queued.command.coalesce_key
                for item in self._pending
            )
            if newer:
                queued.ticket._complete(CommandResult(
                    saved=True, queued=True, error="superseded"
                ))
                return
            if len(self._pending) >= self._queue_size:
                displaced = max(
                    self._pending,
                    key=lambda item: (item.command.priority, item.order),
                )
                self._pending.remove(displaced)
                displaced.ticket._complete(CommandResult(
                    saved=displaced.command.saved,
                    queued=True,
                    applied=False,
                    error="evicted to retain saved state during recovery",
                ))
            self._pending.append(queued)
            self._condition.notify_all()

    def _peek(self) -> Optional[_Queued]:
        with self._condition:
            if not self._pending:
                return None
            return min(self._pending, key=lambda item: (item.command.priority, item.order))

    def _pop(self) -> Optional[_Queued]:
        with self._condition:
            queued = self._peek()
            if queued is not None:
                self._pending.remove(queued)
            return queued

    def _should_stop(self) -> bool:
        with self._condition:
            return self._stop

    def _wait(self, seconds: float) -> bool:
        """Wakeable idle wait; submissions may end it early."""
        with self._condition:
            if self._stop:
                return True
            self._condition.wait(max(0.0, seconds))
            return self._stop

    def _sleep(self, seconds: float) -> bool:
        """A full-duration wait for rate limiting and firmware settling."""
        deadline = time.monotonic() + max(0.0, seconds)
        with self._condition:
            while not self._stop:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def _wait_backoff(self, seconds: float) -> bool:
        """Wait the full reconnect delay; only stop/resume may bypass it."""
        deadline = time.monotonic() + max(0.0, seconds)
        with self._condition:
            while not self._stop:
                if self._resume_requested:
                    self._resume_requested = False
                    return False
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True


__all__ = [
    "ApplyPlan", "CommandTicket", "DeviceCommand", "DeviceStatus",
    "DeviceTransport", "DeviceWorker", "HidTransport", "LatestTelemetry",
    "plan_state_change",
]
