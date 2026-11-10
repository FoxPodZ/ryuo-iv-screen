# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned HTTP API and bounded live-event delivery."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import asdict, dataclass, is_dataclass, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from aiohttp import web

from .device import DeviceCommand
from .models import CommandResult, Measurement, SensorDescriptor, TelemetrySnapshot
from .store import (
    Profile,
    ProfileConflict,
    ProfileNotFound,
    ProfileStore,
    ScreenState,
    StateStore,
)


API_PREFIX = "/api/v1"
_SERIAL_KEYS = frozenset(
    ("serial", "serialnumber", "serial_number", "device_serial", "deviceserial", "sn")
)


class RevisionConflict(RuntimeError):
    """A state mutation was based on a revision that is no longer current."""

    def __init__(self, expected: int, current: int) -> None:
        super().__init__("expected revision {}, current revision {}".format(expected, current))
        self.expected = expected
        self.current = current


@dataclass(frozen=True)
class SseEvent:
    event_id: int
    snapshot: Mapping[str, Any]


class SseSubscription:
    """One newest-only subscriber queue."""

    def __init__(self, hub: "SseHub") -> None:
        self._hub = hub
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._closed = False

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    async def get(self) -> SseEvent:
        return await self._queue.get()

    def _offer(self, event: SseEvent) -> None:
        if self._closed:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - defensive race guard
                pass
        # A client may mutate the decoded object it receives. Never let that
        # corrupt the hub's retained snapshot or another subscriber's view.
        self._queue.put_nowait(
            SseEvent(event.event_id, copy.deepcopy(dict(event.snapshot)))
        )

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._hub._discard(self)


class SseHub:
    """Publish immutable snapshots to bounded newest-only queues."""

    def __init__(self, initial_snapshot: Optional[Mapping[str, Any]] = None) -> None:
        self._last_event_id = 0
        self._latest: Optional[SseEvent] = None
        self._subscribers = set()
        if initial_snapshot is not None:
            self.publish(initial_snapshot)

    @property
    def last_event_id(self) -> int:
        return self._last_event_id

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, snapshot: Mapping[str, Any]) -> int:
        if not isinstance(snapshot, Mapping):
            raise TypeError("SSE snapshot must be an object")
        self._last_event_id += 1
        event = SseEvent(self._last_event_id, copy.deepcopy(dict(snapshot)))
        self._latest = event
        for subscriber in tuple(self._subscribers):
            subscriber._offer(event)
        return event.event_id

    def subscribe(self, last_event_id: Optional[int] = None) -> SseSubscription:
        if last_event_id is not None:
            if isinstance(last_event_id, bool) or not isinstance(last_event_id, int):
                raise TypeError("Last-Event-ID must be an integer")
            if last_event_id < 0:
                raise ValueError("Last-Event-ID cannot be negative")
            if last_event_id > self._last_event_id:
                raise ValueError("Last-Event-ID is ahead of the event stream")
        subscriber = SseSubscription(self)
        self._subscribers.add(subscriber)
        if self._latest is not None and self._latest.event_id != last_event_id:
            subscriber._offer(self._latest)
        return subscriber

    def _discard(self, subscriber: SseSubscription) -> None:
        self._subscribers.discard(subscriber)


@dataclass
class AppContext:
    state_store: StateStore
    profile_store: ProfileStore
    device: Any
    telemetry: Any
    sse: Optional[SseHub] = None
    sse_heartbeat: float = 15.0

    def __post_init__(self) -> None:
        if self.sse_heartbeat <= 0:
            raise ValueError("SSE heartbeat must be positive")
        self.state = self.state_store.load()
        self.mutation_lock = asyncio.Lock()
        self._live_task = None
        if self.sse is None:
            self.sse = SseHub(self.snapshot_document())

    def snapshot_document(self) -> Dict[str, Any]:
        document: Dict[str, Any] = {
            "revision": self.state.revision,
            "state": self.state.to_dict(),
            "device": _device_document(self.device.status()),
        }
        try:
            document["telemetry"] = _telemetry_document(
                self.telemetry.sample(), self.telemetry.catalog()
            )
        except Exception as exc:
            document["telemetry"] = {
                "sampledAt": None,
                "measurements": {},
                "errors": {"collector": str(exc)},
            }
        return document

    def publish_snapshot(self) -> int:
        assert self.sse is not None
        return self.sse.publish(self.snapshot_document())

    @property
    def live_publisher_running(self) -> bool:
        return self._live_task is not None and not self._live_task.done()

    async def start_live_publisher(self) -> None:
        if self.live_publisher_running:
            return
        self._live_task = asyncio.create_task(
            self._live_publisher(), name="ryuo-live-telemetry"
        )

    async def stop_live_publisher(self) -> None:
        task = self._live_task
        if task is None:
            return
        self._live_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _live_publisher(self) -> None:
        while True:
            # State mutations replace the immutable ScreenState, so the next
            # iteration automatically adopts the current telemetry cadence.
            await asyncio.sleep(float(self.state.refresh_interval))
            try:
                self.publish_snapshot()
            except Exception:
                # A transient collector/status error must not terminate live
                # delivery. snapshot_document already records telemetry
                # errors; this guard also isolates an unexpected status source.
                continue


# AppKey avoids accidental collisions on current aiohttp while the string
# fallback keeps the declared aiohttp 3.8 floor usable.
CONTEXT_KEY = (
    web.AppKey("ryuo_screen_context", AppContext)
    if hasattr(web, "AppKey")
    else "ryuo_screen_context"
)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SERIAL_KEYS:
                continue
            result[str(key)] = _redact(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def _status_mapping(status: Any) -> Dict[str, Any]:
    if is_dataclass(status):
        return asdict(status)
    result = {}
    for name in (
        "phase", "connected", "sequence", "queue_depth", "reconnect_count",
        "recovery_count", "last_ack", "heartbeat_age", "last_error", "descriptor",
        "model", "firmware", "uptime",
    ):
        if hasattr(status, name):
            result[name] = getattr(status, name)
    return result


def _device_document(status: Any) -> Dict[str, Any]:
    document = _redact(_status_mapping(status))
    phase = document.get("phase", "unknown")
    document["health"] = phase
    document.setdefault("connected", False)
    document.setdefault("firmware", None)
    return document


def _descriptor_document(descriptor: SensorDescriptor) -> Dict[str, Any]:
    return {
        "ref": descriptor.ref.to_dict(),
        "measurementId": descriptor.measurement_id,
        "label": descriptor.label,
        "unit": descriptor.unit,
        "available": descriptor.available,
        "source": descriptor.source,
        "metadata": copy.deepcopy(dict(descriptor.metadata)),
        "error": descriptor.error,
    }


def _measurement_document(
    measurement: Measurement, source: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ref": measurement.ref.to_dict(),
        "value": measurement.value,
        "unit": measurement.unit,
        "sampledAt": measurement.sampled_at,
        "available": measurement.available,
        "source": source,
        "error": measurement.error,
    }


def _telemetry_document(
    snapshot: TelemetrySnapshot, descriptors: Sequence[SensorDescriptor],
) -> Dict[str, Any]:
    sources = {
        (item.measurement_id, item.ref): item.source for item in descriptors
    }
    return {
        "sampledAt": snapshot.sampled_at,
        "measurements": {
            key: _measurement_document(value, sources.get((key, value.ref)))
            for key, value in sorted(snapshot.measurements.items())
        },
        "errors": dict(snapshot.errors),
    }


def _result_document(result: CommandResult, revision: int) -> Dict[str, Any]:
    return {
        "revision": revision,
        "saved": result.saved,
        "queued": result.queued,
        "applied": result.applied,
        "acked": result.acked,
        "error": result.error,
    }


def _ticket_result(ticket: Any) -> CommandResult:
    if isinstance(ticket, CommandResult):
        return ticket
    if hasattr(ticket, "snapshot"):
        result = ticket.snapshot()
        if isinstance(result, CommandResult):
            return result
    raise TypeError("device submit must return a command result ticket")


async def _json_object(request: web.Request) -> Dict[str, Any]:
    try:
        document = await request.json()
    except Exception as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(document, dict):
        raise TypeError("request body must be an object")
    return document


def _parse_revision(request: web.Request, document: Mapping[str, Any]) -> int:
    raw = request.headers.get("If-Match")
    body_value = document.get("revision")
    if body_value is not None and (
        isinstance(body_value, bool) or not isinstance(body_value, int)
    ):
        raise ValueError("body revision must be an integer")
    if raw is not None:
        raw = raw.strip()
        if raw.startswith("W/"):
            raw = raw[2:].strip()
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            raw = raw[1:-1]
        try:
            header_value = int(raw)
        except ValueError as exc:
            raise ValueError("If-Match must contain an integer revision") from exc
        if body_value is not None and body_value != header_value:
            raise ValueError("body revision and If-Match disagree")
        value = header_value
    else:
        value = body_value
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("a state revision is required")
    if value < 0:
        raise ValueError("revision cannot be negative")
    return value


def _state_from_profile(profile: Profile, revision: int) -> ScreenState:
    document = profile.to_dict()
    for name in ("slug", "name", "factory"):
        document.pop(name, None)
    document["revision"] = revision
    document["active_profile"] = profile.slug
    return ScreenState.from_dict(document)


def _profile_from_request(document: Mapping[str, Any]) -> Profile:
    values = dict(document)
    values["factory"] = False
    return Profile.from_dict(values)


async def _mutate_state(
    request: web.Request, allowed: Sequence[str], transform=None,
) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    document = await _json_object(request)
    expected = _parse_revision(request, document)
    changes = {key: value for key, value in document.items() if key != "revision"}
    unknown = set(changes) - set(allowed)
    if unknown:
        raise ValueError("unknown fields: {}".format(", ".join(sorted(unknown))))
    async with context.mutation_lock:
        current = context.state
        if expected != current.revision:
            raise RevisionConflict(expected, current.revision)
        if transform is None:
            new_state = replace(current, revision=current.revision + 1, **changes)
        else:
            new_state = transform(current, changes)
        context.state_store.save(new_state)
        context.state = new_state
        ticket = context.device.submit(DeviceCommand.for_state(new_state))
        result = _ticket_result(ticket)
        context.publish_snapshot()
        return web.json_response(_result_document(result, new_state.revision))


@web.middleware
async def _errors(request: web.Request, handler):
    try:
        return await handler(request)
    except RevisionConflict as exc:
        return web.json_response(
            {
                "error": "revision_conflict",
                "message": str(exc),
                "expectedRevision": exc.expected,
                "currentRevision": exc.current,
            },
            status=409,
        )
    except ProfileNotFound as exc:
        return web.json_response(
            {"error": "not_found", "message": "profile {!r} was not found".format(exc.args[0])},
            status=404,
        )
    except ProfileConflict as exc:
        return web.json_response(
            {"error": "conflict", "message": str(exc)}, status=409
        )
    except PermissionError as exc:
        return web.json_response(
            {"error": "forbidden", "message": str(exc)}, status=403
        )
    except (TypeError, ValueError, KeyError) as exc:
        return web.json_response(
            {"error": "validation_error", "message": str(exc)}, status=400
        )


async def _get_state(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    return web.json_response({"revision": context.state.revision, "state": context.state.to_dict()})


async def _get_telemetry(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    descriptors = tuple(context.telemetry.catalog())
    return web.json_response(_telemetry_document(context.telemetry.sample(), descriptors))


async def _get_sensors(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    return web.json_response(
        {"sensors": [_descriptor_document(item) for item in context.telemetry.catalog()]}
    )


async def _get_device(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    return web.json_response(_device_document(context.device.status()))


async def _patch_brightness(request: web.Request) -> web.Response:
    return await _mutate_state(request, ("brightness",))


async def _patch_screen(request: web.Request) -> web.Response:
    return await _mutate_state(
        request,
        (
            "screen_mode", "media", "playback_modes", "slots", "title_colors",
            "content_colors", "opacity", "rgb_mode", "rgb_target", "thermal_source",
        ),
    )


async def _patch_telemetry_settings(request: web.Request) -> web.Response:
    return await _mutate_state(
        request, ("temperature_unit", "refresh_interval", "sensor_selectors", "slots")
    )


async def _list_profiles(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    return web.json_response(
        {"profiles": [item.to_dict() for item in context.profile_store.list()]}
    )


async def _create_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    profile = context.profile_store.create(_profile_from_request(await _json_object(request)))
    return web.json_response({"profile": profile.to_dict()}, status=201)


async def _get_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    return web.json_response(
        {"profile": context.profile_store.get(request.match_info["slug"]).to_dict()}
    )


async def _update_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    current = context.profile_store.get(request.match_info["slug"])
    changes = await _json_object(request)
    merged = current.to_dict()
    unknown = set(changes) - set(merged)
    if unknown:
        raise ValueError("unknown profile fields: {}".format(", ".join(sorted(unknown))))
    merged.update(changes)
    profile = context.profile_store.update(
        request.match_info["slug"], _profile_from_request(merged)
    )
    return web.json_response({"profile": profile.to_dict()})


async def _delete_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    context.profile_store.delete(request.match_info["slug"])
    return web.Response(status=204)


async def _duplicate_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    document = await _json_object(request)
    unknown = set(document) - {"name", "slug"}
    if unknown:
        raise ValueError("unknown fields: {}".format(", ".join(sorted(unknown))))
    if "name" not in document:
        raise ValueError("duplicate profile name is required")
    profile = context.profile_store.duplicate(
        request.match_info["slug"], document["name"], document.get("slug")
    )
    return web.json_response({"profile": profile.to_dict()}, status=201)


async def _import_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    profile = context.profile_store.import_profile(await _json_object(request))
    return web.json_response({"profile": profile.to_dict()}, status=201)


async def _export_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    return web.Response(
        text=context.profile_store.export_profile(request.match_info["slug"]),
        content_type="application/json",
    )


async def _apply_profile(request: web.Request) -> web.Response:
    context: AppContext = request.app[CONTEXT_KEY]
    document = await _json_object(request)
    expected = _parse_revision(request, document)
    unknown = set(document) - {"revision"}
    if unknown:
        raise ValueError("unknown fields: {}".format(", ".join(sorted(unknown))))
    async with context.mutation_lock:
        current = context.state
        if expected != current.revision:
            raise RevisionConflict(expected, current.revision)
        profile = context.profile_store.get(request.match_info["slug"])
        new_state = _state_from_profile(profile, current.revision + 1)
        context.state_store.save(new_state)
        context.state = new_state
        result = _ticket_result(context.device.submit(DeviceCommand.for_state(new_state)))
        context.publish_snapshot()
        return web.json_response(_result_document(result, new_state.revision))


async def _events(request: web.Request) -> web.StreamResponse:
    context: AppContext = request.app[CONTEXT_KEY]
    raw_last = request.headers.get("Last-Event-ID")
    last_id = None
    if raw_last is not None:
        try:
            last_id = int(raw_last)
        except ValueError as exc:
            raise ValueError("Last-Event-ID must be an integer") from exc
    assert context.sse is not None
    subscriber = context.sse.subscribe(last_id)
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
    prepared = False
    try:
        await response.prepare(request)
        prepared = True
        while True:
            try:
                event = await asyncio.wait_for(subscriber.get(), context.sse_heartbeat)
            except asyncio.TimeoutError:
                await response.write(b": heartbeat\n\n")
                continue
            payload = json.dumps(event.snapshot, ensure_ascii=False, separators=(",", ":"))
            data = "id: {}\nevent: snapshot\ndata: {}\n\n".format(event.event_id, payload)
            await response.write(data.encode("utf-8"))
    except asyncio.CancelledError:
        raise
    except (ConnectionResetError, BrokenPipeError):
        if not prepared:
            raise
    finally:
        subscriber.close()
    return response


async def _live_events_context(app: web.Application):
    context: AppContext = app[CONTEXT_KEY]
    await context.start_live_publisher()
    try:
        yield
    finally:
        await context.stop_live_publisher()


def create_app(context: AppContext) -> web.Application:
    if not isinstance(context, AppContext):
        raise TypeError("context must be AppContext")
    app = web.Application(middlewares=[_errors])
    app[CONTEXT_KEY] = context
    app.cleanup_ctx.append(_live_events_context)
    app.router.add_get(API_PREFIX + "/state", _get_state)
    app.router.add_get(API_PREFIX + "/telemetry", _get_telemetry)
    app.router.add_get(API_PREFIX + "/sensors", _get_sensors)
    app.router.add_get(API_PREFIX + "/device", _get_device)
    app.router.add_get(API_PREFIX + "/events", _events)
    app.router.add_patch(API_PREFIX + "/brightness", _patch_brightness)
    app.router.add_patch(API_PREFIX + "/screen", _patch_screen)
    app.router.add_patch(API_PREFIX + "/telemetry-settings", _patch_telemetry_settings)
    app.router.add_get(API_PREFIX + "/profiles", _list_profiles)
    app.router.add_post(API_PREFIX + "/profiles", _create_profile)
    app.router.add_post(API_PREFIX + "/profiles/import", _import_profile)
    app.router.add_get(API_PREFIX + "/profiles/{slug}/export", _export_profile)
    app.router.add_post(API_PREFIX + "/profiles/{slug}/apply", _apply_profile)
    app.router.add_post(API_PREFIX + "/profiles/{slug}/duplicate", _duplicate_profile)
    app.router.add_get(API_PREFIX + "/profiles/{slug}", _get_profile)
    app.router.add_patch(API_PREFIX + "/profiles/{slug}", _update_profile)
    app.router.add_delete(API_PREFIX + "/profiles/{slug}", _delete_profile)
    return app


__all__ = [
    "API_PREFIX", "AppContext", "RevisionConflict", "SseEvent", "SseHub",
    "SseSubscription", "create_app",
]
