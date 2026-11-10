# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from dataclasses import replace

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ryuo_screen.api import AppContext, create_app
from ryuo_screen.device import DeviceStatus
from ryuo_screen.models import (
    CommandResult,
    Measurement,
    SensorDescriptor,
    SensorRef,
    TelemetrySnapshot,
)
from ryuo_screen.store import ProfileStore, ScreenState, StateStore


class FakeTicket:
    def __init__(self, result):
        self._result = result

    def snapshot(self):
        return self._result


class FakeDevice:
    def __init__(self):
        self.commands = []
        self.state_seen_on_submit = []
        self.store = None

    def submit(self, command):
        self.commands.append(command)
        if self.store is not None:
            self.state_seen_on_submit.append(self.store.load())
        return FakeTicket(CommandResult(saved=True, queued=True, applied=False, acked=False))

    def status(self):
        return DeviceStatus(
            phase="healthy",
            connected=True,
            sequence=17,
            last_ack=16,
            descriptor={"model": "Ryuo IV", "nested": {"serial": "SECRET"}},
            model="Ryuo IV",
            firmware="1.2.3",
        )


class FakeTelemetry:
    def __init__(self):
        self.ref = SensorRef("amd", "0000:03:00.0", "temp1_input")
        self.snapshot_value = TelemetrySnapshot(
            {
                "gpu.temperature": Measurement(
                    self.ref,
                    "gpu.temperature",
                    None,
                    "C",
                    100.0,
                    available=False,
                    error="permission denied",
                )
            },
            100.0,
            {"amd": "partial sample"},
        )

    def sample(self):
        return self.snapshot_value

    def catalog(self):
        return (
            SensorDescriptor(
                self.ref,
                "gpu.temperature",
                "GPU Temperature",
                "C",
                available=False,
                source="/sys/devices/pci0000:00/0000:03:00.0/hwmon/temp1_input",
                error="permission denied",
            ),
        )


async def _client(tmp_path, state=None):
    state_store = StateStore(tmp_path / "state.json")
    state_store.save(state or ScreenState(revision=4))
    device = FakeDevice()
    device.store = state_store
    context = AppContext(
        state_store=state_store,
        profile_store=ProfileStore(tmp_path / "profiles"),
        device=device,
        telemetry=FakeTelemetry(),
    )
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    return client, context, device


@pytest.mark.asyncio
async def test_read_routes_expose_revision_health_sources_and_unavailable_reason(tmp_path):
    client, _, _ = await _client(tmp_path)
    try:
        state = await (await client.get("/api/v1/state")).json()
        telemetry = await (await client.get("/api/v1/telemetry")).json()
        sensors = await (await client.get("/api/v1/sensors")).json()
        device = await (await client.get("/api/v1/device")).json()
    finally:
        await client.close()

    assert state["revision"] == 4
    assert state["state"]["brightness"] == 85
    assert "serial" not in str(state).lower()
    reading = telemetry["measurements"]["gpu.temperature"]
    assert reading["available"] is False
    assert reading["error"] == "permission denied"
    assert reading["source"].endswith("temp1_input")
    assert sensors["sensors"][0]["ref"]["device"] == "0000:03:00.0"
    assert sensors["sensors"][0]["source"].startswith("/sys/")
    assert device["connected"] is True
    assert device["health"] == "healthy"
    assert device["firmware"] == "1.2.3"
    assert "SECRET" not in str(device)


@pytest.mark.asyncio
async def test_state_mutation_saves_before_queue_and_returns_truthful_flags(tmp_path):
    client, context, device = await _client(tmp_path)
    try:
        response = await client.patch(
            "/api/v1/brightness",
            headers={"If-Match": '"4"'},
            json={"brightness": 42},
        )
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 200
    assert body == {
        "revision": 5,
        "saved": True,
        "queued": True,
        "applied": False,
        "acked": False,
        "error": None,
    }
    assert context.state_store.load().brightness == 42
    assert device.state_seen_on_submit[0].revision == 5
    assert device.state_seen_on_submit[0].brightness == 42
    assert device.commands[0].state.revision == 5


@pytest.mark.asyncio
async def test_stale_concurrent_client_gets_current_revision_without_mutation(tmp_path):
    client, context, device = await _client(tmp_path)
    try:
        first, second = await asyncio.gather(
            client.patch(
                "/api/v1/brightness",
                headers={"If-Match": "4"},
                json={"brightness": 21},
            ),
            client.patch(
                "/api/v1/brightness",
                headers={"If-Match": "4"},
                json={"brightness": 99},
            ),
        )
        first_body, second_body = await first.json(), await second.json()
    finally:
        await client.close()

    responses = sorted(
        ((first.status, first_body), (second.status, second_body)), key=lambda item: item[0]
    )
    assert [item[0] for item in responses] == [200, 409]
    conflict = responses[1][1]
    assert conflict["error"] == "revision_conflict"
    assert conflict["currentRevision"] == 5
    assert context.state_store.load().revision == 5
    assert context.state_store.load().brightness in (21, 99)
    assert len(device.commands) == 1


@pytest.mark.asyncio
async def test_screen_patch_validates_before_saving(tmp_path):
    client, context, device = await _client(tmp_path)
    original = context.state_store.path.read_bytes()
    try:
        response = await client.patch(
            "/api/v1/screen",
            headers={"If-Match": "4"},
            json={"screen_mode": "Screen Splitting", "media": [["a.mp4"]]},
        )
        body = await response.json()
    finally:
        await client.close()
    assert response.status == 400
    assert body["error"] == "validation_error"
    assert context.state_store.path.read_bytes() == original
    assert device.commands == []


@pytest.mark.asyncio
async def test_boolean_body_revision_cannot_alias_integer_if_match(tmp_path):
    client, context, device = await _client(tmp_path)
    try:
        response = await client.patch(
            "/api/v1/brightness",
            headers={"If-Match": "1"},
            json={"revision": True, "brightness": 42},
        )
        body = await response.json()
    finally:
        await client.close()
    assert response.status == 400
    assert body["error"] == "validation_error"
    assert context.state_store.load().revision == 4
    assert device.commands == []
