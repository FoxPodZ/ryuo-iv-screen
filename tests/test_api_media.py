# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import asyncio
import time

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ryuo_screen.api import AppContext, create_app
from ryuo_screen.device import DeviceStatus, LatestTelemetry
from ryuo_screen.media import MediaBusy, MediaCatalog, MediaManager
from ryuo_screen.models import CommandResult, TelemetrySnapshot
from ryuo_screen.store import ProfileStore, ScreenState, StateStore


class Ticket:
    def __init__(self, result):
        self.value = result

    def snapshot(self):
        return self.value

    def wait(self, timeout=None):
        return self.value


class Device:
    def __init__(self):
        self.custom = []
        self.preset = ["RyUO_MIKU.mp4"]
        self.commands = []

    def status(self):
        return DeviceStatus(phase="healthy", connected=True, descriptor={
            "media": {"preset": list(self.preset), "custom": list(self.custom)}
        })

    def latest_telemetry(self):
        return LatestTelemetry(TelemetrySnapshot({}, 1.0), (), None)

    def submit(self, command):
        self.commands.append(command)
        name = command.payload["include"][0]
        if name in self.custom:
            self.custom.remove(name)
        return Ticket(CommandResult(saved=False, queued=True, applied=True, acked=True))


class Tools:
    def status(self):
        return {"ffprobe": True, "ffmpeg": True}

    def probe(self, path):
        from ryuo_screen.media import MediaInfo
        return MediaInfo("source", "png", "png", "rgba", 2240, 1080, None, Path(path).stat().st_size)

    def plan(self, info):
        from ryuo_screen.media import ConversionPlan
        return ConversionPlan("passthrough", ".png")

    def thumbnail(self, source, destination, **kwargs):
        Path(destination).write_bytes(b"jpeg-preview")
        return Path(destination)

    def proxy(self, source, destination, **kwargs):
        Path(destination).write_bytes(b"mp4-proxy")
        return Path(destination)


class Adb:
    def __init__(self, device, success=True, refresh=True):
        self.device = device
        self.success = success
        self.refresh = refresh

    def available(self):
        return type("Availability", (), {"available": True, "reason": None, "serial": "A"})()

    def push(self, source, name, *, target):
        assert target.serial == "A"
        if self.success and self.refresh:
            self.device.custom.append(name)
        return self.success

    def pull(self, name, destination, *, factory=False, max_bytes=None):
        Path(destination).write_bytes(b"device-media")
        return True


async def _client(tmp_path, adb_success=True, refresh=True):
    state = StateStore(tmp_path / "state.json")
    state.save(ScreenState())
    device = Device()
    manager = MediaManager(
        tmp_path / "jobs", Tools(), Adb(device, adb_success, refresh), device,
        catalog_loader=lambda: MediaCatalog.from_conn(device.status().descriptor),
        max_bytes=64,
    )
    context = AppContext(state, ProfileStore(tmp_path / "profiles"), device, object(), media=manager)
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    return client, context, device


@pytest.mark.asyncio
async def test_media_list_upload_truthfulness_and_refresh(tmp_path):
    client, _, device = await _client(tmp_path)
    try:
        listing = await (await client.get("/api/v1/media")).json()
        response = await client.post(
            "/api/v1/media/upload", data=b"image", headers={"X-Filename": "../../bad;name.png"}
        )
        body = await response.json()
        job_response = await client.get("/api/v1/media/jobs/{}".format(body["jobId"]))
        job_body = await job_response.json()
        refreshed = await (await client.get("/api/v1/media")).json()
    finally:
        await client.close()
    assert listing["factory"] == ["RyUO_MIKU.mp4"] and listing["custom"] == []
    assert response.status == 201
    assert body["applied"] is True and body["confirmed"] is True
    assert job_response.status == 200 and job_body == body
    assert body["name"] in refreshed["custom"] == device.custom
    assert "bad" not in body["name"]


@pytest.mark.asyncio
async def test_upload_never_reports_applied_before_push_and_refreshed_listing(tmp_path):
    for success, refresh in ((False, False), (True, False)):
        client, _, _ = await _client(tmp_path / ("x" + str(success) + str(refresh)), success, refresh)
        try:
            response = await client.post("/api/v1/media/upload", data=b"image", headers={"X-Filename": "x.png"})
            body = await response.json()
        finally:
            await client.close()
        assert body["applied"] is False
        assert body["confirmed"] is False


@pytest.mark.asyncio
async def test_delete_only_confirmed_custom_and_waits_for_refresh(tmp_path):
    client, _, device = await _client(tmp_path)
    device.custom.append("mine.png")
    try:
        factory = await client.delete("/api/v1/media/RyUO_MIKU.mp4")
        unknown = await client.delete("/api/v1/media/nope.png")
        deleted = await client.delete("/api/v1/media/mine.png")
        body = await deleted.json()
    finally:
        await client.close()
    assert factory.status == 403
    assert unknown.status == 404
    assert deleted.status == 200
    assert body["applied"] is True and body["confirmed"] is True
    assert device.commands[0].resource == "mediaDelete"


@pytest.mark.asyncio
async def test_media_api_requires_configured_pipeline(tmp_path):
    state = StateStore(tmp_path / "state.json")
    state.save(ScreenState())
    device = Device()
    context = AppContext(state, ProfileStore(tmp_path / "profiles"), device, object())
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    try:
        response = await client.get("/api/v1/media")
        body = await response.json()
    finally:
        await client.close()
    assert response.status == 503
    assert body["error"] == "media_unavailable"


@pytest.mark.asyncio
async def test_media_preview_routes_and_busy_status_are_bounded(tmp_path):
    client, context, device = await _client(tmp_path)
    device.custom.append("mine.png")
    try:
        thumbnail = await client.get("/api/v1/media/preview/thumbnail/RyUO_MIKU.mp4")
        thumbnail_body = await thumbnail.read()
        proxy = await client.get("/api/v1/media/preview/proxy/mine.png")
        proxy_body = await proxy.read()
        missing = await client.get("/api/v1/media/preview/thumbnail/nope.png")

        async def busy(stream, original_name):
            raise MediaBusy("media job capacity is full")

        context.media.upload = busy
        rejected = await client.post("/api/v1/media/upload", data=b"x")
        rejected_body = await rejected.json()
    finally:
        await client.close()
    assert thumbnail.status == 200 and thumbnail_body == b"jpeg-preview"
    assert thumbnail.content_type == "image/jpeg"
    assert proxy.status == 200 and proxy_body == b"mp4-proxy"
    assert proxy.content_type == "video/mp4"
    assert missing.status == 404
    assert rejected.status == 429
    assert rejected_body["error"] == "media_busy"


@pytest.mark.asyncio
async def test_media_listing_does_not_block_event_loop_on_adb_probe(tmp_path):
    client, context, _ = await _client(tmp_path)

    def slow_available():
        time.sleep(0.2)
        return type("Availability", (), {
            "available": True, "reason": None, "serial": "A",
        })()

    context.media.adb.available = slow_available
    ticks = 0

    async def ticker():
        nonlocal ticks
        for _ in range(5):
            await asyncio.sleep(0.01)
            ticks += 1

    request_task = asyncio.create_task(client.get("/api/v1/media"))
    ticker_task = asyncio.create_task(ticker())
    try:
        await asyncio.sleep(0.06)
        assert ticks == 5
        assert not request_task.done()
        response = await request_task
        await ticker_task
        await response.json()
    finally:
        if not request_task.done():
            request_task.cancel()
        if not ticker_task.done():
            ticker_task.cancel()
        await client.close()
