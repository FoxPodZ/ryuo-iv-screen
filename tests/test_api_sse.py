# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ryuo_screen.api import AppContext, SseHub, create_app
from ryuo_screen.device import DeviceStatus
from ryuo_screen.models import TelemetrySnapshot
from ryuo_screen.store import ProfileStore, ScreenState, StateStore


@pytest.mark.asyncio
async def test_hub_initial_reconnect_and_slow_subscriber_keeps_only_newest():
    source = {"revision": 1, "nested": {"value": "original"}}
    hub = SseHub(source)
    source["nested"]["value"] = "mutated"
    slow = hub.subscribe()
    first = await slow.get()
    assert first.event_id == 1
    assert first.snapshot["nested"]["value"] == "original"
    first.snapshot["nested"]["value"] = "subscriber mutation"
    isolated = hub.subscribe(last_event_id=0)
    assert (await isolated.get()).snapshot["nested"]["value"] == "original"
    isolated.close()

    id2 = hub.publish({"revision": 2})
    id3 = hub.publish({"revision": 3})
    latest = await slow.get()
    assert (id2, id3, latest.event_id, latest.snapshot["revision"]) == (2, 3, 3, 3)
    assert slow.queue_size == 0

    reconnect = hub.subscribe(last_event_id=2)
    replay = await reconnect.get()
    assert replay.event_id == 3
    reconnect.close()
    slow.close()
    assert hub.subscriber_count == 0
    with pytest.raises(ValueError):
        hub.subscribe(last_event_id=99)


class _Device:
    def __init__(self):
        self.submit_count = 0

    def status(self):
        return DeviceStatus()


class _Telemetry:
    def sample(self):
        return TelemetrySnapshot({}, 1.0)

    def catalog(self):
        return ()


@pytest.mark.asyncio
async def test_sse_endpoint_emits_snapshot_heartbeat_and_cleans_disconnect(tmp_path):
    state_store = StateStore(tmp_path / "state.json")
    state_store.save(ScreenState())
    context = AppContext(
        state_store,
        ProfileStore(tmp_path / "profiles"),
        _Device(),
        _Telemetry(),
        sse_heartbeat=0.02,
    )
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    try:
        response = await client.get("/api/v1/events")
        assert (await response.content.readline()).startswith(b"id: 1")
        assert (await response.content.readline()).startswith(b"event: snapshot")
        assert (await response.content.readline()).startswith(b"data: ")
        await response.content.readline()
        response.close()
        for _ in range(50):
            if context.sse.subscriber_count == 0:
                break
            await asyncio.sleep(0.01)
        assert context.sse.subscriber_count == 0

        current_id = context.sse.last_event_id
        heartbeat = await client.get(
            "/api/v1/events", headers={"Last-Event-ID": str(current_id)}
        )
        line = await asyncio.wait_for(heartbeat.content.readline(), 0.5)
        assert line.startswith(b": heartbeat")
        heartbeat.close()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_app_lifecycle_publishes_live_telemetry_without_mutations_and_stops(tmp_path):
    class ChangingTelemetry(_Telemetry):
        def __init__(self):
            self.samples = 0

        def sample(self):
            self.samples += 1
            return TelemetrySnapshot({}, float(self.samples))

    telemetry = ChangingTelemetry()
    state_store = StateStore(tmp_path / "state.json")
    state_store.save(ScreenState(refresh_interval=0.02))
    context = AppContext(
        state_store,
        ProfileStore(tmp_path / "profiles"),
        _Device(),
        telemetry,
    )
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    try:
        initial_id = context.sse.last_event_id
        for _ in range(100):
            if context.sse.last_event_id >= initial_id + 3:
                break
            await asyncio.sleep(0.01)
        assert context.sse.last_event_id >= initial_id + 3
        assert telemetry.samples >= 4  # initial snapshot plus periodic updates
        assert context.live_publisher_running
    finally:
        await client.close()
    stopped_id = context.sse.last_event_id
    assert not context.live_publisher_running
    await asyncio.sleep(0.05)
    assert context.sse.last_event_id == stopped_id


@pytest.mark.asyncio
async def test_prepare_failure_does_not_leak_sse_subscriber(tmp_path, monkeypatch):
    state_store = StateStore(tmp_path / "state.json")
    state_store.save(ScreenState())
    context = AppContext(
        state_store,
        ProfileStore(tmp_path / "profiles"),
        _Device(),
        _Telemetry(),
    )
    original_prepare = web.StreamResponse.prepare

    async def fail_event_stream_prepare(response, request):
        if response.headers.get("Content-Type") == "text/event-stream":
            raise ConnectionResetError("client left before headers")
        return await original_prepare(response, request)

    monkeypatch.setattr(web.StreamResponse, "prepare", fail_event_stream_prepare)
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    try:
        try:
            response = await client.get("/api/v1/events")
        except (aiohttp.ClientError, ConnectionResetError):
            pass
        else:
            assert response.status >= 500
            await response.read()
        for _ in range(50):
            if context.sse.subscriber_count == 0:
                break
            await asyncio.sleep(0.01)
        assert context.sse.subscriber_count == 0
    finally:
        await client.close()
