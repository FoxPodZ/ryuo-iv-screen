# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import asyncio
import subprocess
import time

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ryuo_screen.api import AppContext, create_app
from ryuo_screen.device import DeviceStatus, LatestTelemetry
from ryuo_screen.media import AdbAvailability, MediaBusy, MediaCatalog, MediaManager
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
        return AdbAvailability(True, serial="A")

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
    import re
    assert re.fullmatch(r"user-[0-9a-f]{32}\.png", body["name"])


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

        async def busy(stream, original_name, target_token=None):
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
        return AdbAvailability(True, serial="A")

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


@pytest.mark.asyncio
async def test_status_target_is_required_and_cannot_retarget_a_later_upload(tmp_path, monkeypatch):
    from ryuo_screen import media

    client, context, device = await _client(tmp_path)
    port = tmp_path / "usb/1-3"
    port.mkdir(parents=True)
    (port / "idVendor").write_text("0b05")
    (port / "idProduct").write_text("1c76")
    serial = port / "serial"
    serial.write_text("FIRST")
    monkeypatch.setattr(media, "USB_DEVICES", port.parent)
    pushes = []

    def adb(argv, **kwargs):
        if argv[1:] == ["devices", "-l"]:
            current = serial.read_text()
            tid = 7 if current == "FIRST" else 9
            stdout = "List of devices attached\n{} device usb:1-3 transport_id:{}\n".format(current, tid)
        else:
            pushes.append(argv)
            device.custom.append(Path(argv[-1]).name)
            stdout = ""
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    context.media.adb = media.AdbBackend(runner=adb, which=lambda _: "adb")

    async def status():
        return (await (await client.get("/api/v1/media")).json())["adb"]

    async def upload(token):
        headers = {"Content-Type": "application/octet-stream"}
        if token is not None:
            headers["X-Ryuo-Media-Target"] = token
        return await client.post("/api/v1/media/upload", headers=headers, data=b"image")

    try:
        first = await status()
        assert first["serial"] == "FIRST"
        first_token = first["targetToken"]
        assert (await status())["targetToken"] == first_token
        serial.write_text("SECOND")
        assert (await upload(first_token)).status == 409
        assert not pushes
        second = await status()
        second_token = second["targetToken"]
        assert first_token and second_token != first_token
        assert not any(part in second_token for part in ("SECOND", "1-3"))
        for invalid in (None, "wrong", first_token):
            assert (await upload(invalid)).status == 409
        assert not pushes
        assert (await upload(second_token)).status == 201
        assert [argv[1:3] for argv in pushes] == [["-t", "9"]]
        # Observing disappearance invalidates the token even if the next ADB
        # server happens to reuse the same transport ID for the same device.
        serial.write_text("")
        assert not (await status())["available"]
        assert (await upload(None)).status == 409
        serial.write_text("SECOND")
        assert (await upload(second_token)).status == 409
        fresh = await status()
        assert fresh["targetToken"] != second_token
        assert len(pushes) == 1
        # The explicit operator selection continues to work without a status token.
        context.media.adb.serial = "SECOND"
        assert "targetToken" not in await status()
        assert (await upload(None)).status == 201
        assert pushes[-1][1:3] == ["-s", "SECOND"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_disconnected_delete_rejects_stale_listing(tmp_path):
    client, _, device = await _client(tmp_path)
    async with client:
        device.status = lambda: DeviceStatus(connected=False, descriptor={"media": {"custom": ["old.png"], "preset": []}})
        resp = await client.delete("/api/v1/media/old.png")
        assert resp.status == 409
        assert not device.commands


@pytest.mark.asyncio
async def test_preview_checks_final_size_before_returning_bytes(tmp_path, monkeypatch):
    from ryuo_screen import media
    monkeypatch.setattr(media, "MAX_THUMBNAIL_BYTES", 5)
    client, _, _ = await _client(tmp_path)
    async with client:
        resp = await client.get("/api/v1/media/preview/thumbnail/RyUO_MIKU.mp4")
        assert resp.status == 502


@pytest.mark.asyncio
async def test_detached_status_failure_is_logged(tmp_path, caplog):
    import threading
    started, release = threading.Event(), threading.Event()
    client, context, _ = await _client(tmp_path)
    def probe():
        started.set()
        release.wait(1)
        raise RuntimeError("probe failure")
    context.media.adb.available = probe
    async with client:
        pending = asyncio.create_task(context.media.adb_status())
        while not started.is_set():
            await asyncio.sleep(.005)
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        release.set()
        for _ in range(50):
            if "ADB status probe failed" in caplog.text:
                break
            await asyncio.sleep(.005)
        assert "ADB status probe failed" in caplog.text


@pytest.mark.asyncio
async def test_preview_work_leaves_single_default_executor_slot_free(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
    started, release = threading.Event(), threading.Event()
    client, ctx, _ = await _client(tmp_path)
    thumbnail = ctx.media.tools.thumbnail

    def delayed_thumbnail(*args):
        started.set()
        release.wait(1)
        return thumbnail(*args)

    ctx.media.tools.thumbnail = delayed_thumbnail
    async with client:
        preview = asyncio.create_task(ctx.media.preview("RyUO_MIKU.mp4", "thumbnail"))
        try:
            while not started.is_set():
                await asyncio.sleep(.005)
            assert await asyncio.wait_for(loop.run_in_executor(None, lambda: True), .25)
        finally:
            release.set()
            await preview


@pytest.mark.asyncio
async def test_abandoned_delete_marks_pending_ticket_cancelled(tmp_path):
    from ryuo_screen.device import CommandTicket
    from ryuo_screen.media import MediaOperationError
    client, ctx, device = await _client(tmp_path)
    device.custom.append("old.png")
    ticket = CommandTicket()
    device.submit = lambda command: ticket
    try:
        with pytest.raises(MediaOperationError, match="client disconnected"):
            await asyncio.wait_for(ctx.media.delete("old.png", client_gone=lambda: True), .3)
        assert ticket.cancelled.is_set()
    finally:
        await client.close()
