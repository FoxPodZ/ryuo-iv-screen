# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import subprocess
import threading
import time
from pathlib import Path

import pytest

from ryuo_screen.media import (
    AdbAvailability, AdbBackend, MediaBusy, MediaCatalog, MediaInfo, MediaJob, MediaManager,
    MediaTargetChanged, MediaTools,
)


class Result:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class Stream:
    def __init__(self, chunks, delay=0):
        self.chunks = list(chunks)
        self.delay = delay

    async def read(self, size):
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.chunks.pop(0) if self.chunks else b""


class FakeTools(MediaTools):
    def __init__(self):
        self.convert_calls = []

    def probe(self, path):
        return MediaInfo(Path(path).name, "mp4", "h264", "yuv420p", 1920, 1080, 1.0, Path(path).stat().st_size)

    def plan(self, info):
        return super().plan(info)

    def convert(self, source, destination, plan=None, max_bytes=None):
        self.convert_calls.append((Path(source), Path(destination), plan, max_bytes))
        Path(destination).write_bytes(Path(source).read_bytes())
        return Path(destination)


class FakeAdb:
    def __init__(self, outcome=True):
        self.outcome = outcome
        self.calls = []

    def available(self):
        return AdbAvailability(True, serial="A")

    def push(self, source, name, *, target):
        assert target == self.available()
        self.calls.append((Path(source), name))
        return self.outcome


@pytest.mark.asyncio
@pytest.mark.parametrize("hostile", ["../x", "a/b", "a\\b", "a\x00b", "x';rm", 'x";echo', "тест.mp4"])
async def test_job_never_uses_client_name_as_path_or_command(tmp_path, hostile):
    adb = FakeAdb()
    custom = []

    def refresh():
        custom[:] = [adb.calls[-1][1]]
        return MediaCatalog((), tuple(custom))

    job = MediaJob(tmp_path, FakeTools(), adb, refresh, max_bytes=32, idle_timeout=0.1)
    result = await job.run(Stream([b"video"]), hostile)
    assert result.applied is True
    pushed_path, destination = adb.calls[0]
    assert hostile not in str(pushed_path)
    assert hostile not in destination
    assert "/" not in destination and "\\" not in destination and "\x00" not in destination
    assert destination.startswith("user-") and destination.endswith(".mp4")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_job_enforces_byte_and_idle_limits_and_cleans_tempdir(tmp_path):
    job = MediaJob(tmp_path, FakeTools(), FakeAdb(), lambda: MediaCatalog(), max_bytes=4, idle_timeout=0.01)
    with pytest.raises(ValueError, match="size"):
        await job.run(Stream([b"12345"]), "x.mp4")
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(TimeoutError):
        await job.run(Stream([b"x"], delay=0.05), "x.mp4")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_job_cancellation_cleans_tempdir(tmp_path):
    job = MediaJob(tmp_path, FakeTools(), FakeAdb(), lambda: MediaCatalog(), idle_timeout=1)
    task = asyncio.create_task(job.run(Stream([b"x"], delay=1), "x.mp4"))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert list(tmp_path.iterdir()) == []


def test_adb_availability_selection_and_argv_push(tmp_path):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[-2:] == ["devices", "-l"]:
            return Result("List of devices attached\nA\tdevice product:x\nB\tdevice product:y\n")
        return Result("1 file pushed")

    ambiguous = AdbBackend(runner=run, which=lambda name: "/bin/adb")
    assert ambiguous.available().available is False
    selected = AdbBackend(serial="B", runner=run, which=lambda name: "/bin/adb")
    assert selected.available().available is True
    source = tmp_path / "safe"
    source.write_bytes(b"x")
    assert selected.push(source, "user-1.mp4") is True
    argv, kwargs = calls[-1]
    assert argv == ["/bin/adb", "-s", "B", "push", str(source), "/sdcard/pcMedia/user-1.mp4"]
    assert "shell" not in kwargs


def test_adb_pull_uses_selected_device_and_exact_safe_remote_directory(tmp_path):
    calls = []

    def run(argv, **kwargs):
        return Result("List of devices attached\nA\tdevice product:x\n")

    class Process:
        returncode = 0

        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))
            Path(argv[-1]).write_bytes(b"media")

        def poll(self):
            return self.returncode

        def communicate(self):
            return ("", "")

        def kill(self):
            self.returncode = -9

    adb = AdbBackend(
        serial="A", runner=run, popen=Process, which=lambda name: "/bin/adb",
    )
    custom = tmp_path / "custom.bin"
    factory = tmp_path / "factory.bin"
    assert adb.pull("odd;name.mp4", custom, max_bytes=16) is True
    assert adb.pull("MiKu.PNG", factory, factory=True, max_bytes=16) is True
    assert calls[0][0] == [
        "/bin/adb", "-s", "A", "pull", "/sdcard/pcMedia/odd;name.mp4", str(custom),
    ]
    assert calls[1][0] == [
        "/bin/adb", "-s", "A", "pull", "/sdcard/pcMediaPreset/MiKu.PNG", str(factory),
    ]
    assert all("shell" not in kwargs for _, kwargs in calls)


def test_adb_pull_cannot_deadlock_on_progress_larger_than_pipe_capacity(tmp_path):
    progress = b"x" * (1024 * 1024)

    def run(argv, **kwargs):
        return Result("List of devices attached\nA\tdevice product:x\n")

    class NoisyProcess:
        def __init__(self, argv, **kwargs):
            self.returncode = 0
            self.blocked = kwargs.get("stdout") == subprocess.PIPE and len(progress) > 65536
            Path(argv[-1]).write_bytes(b"valid-media")

        def poll(self):
            return None if self.blocked else self.returncode

        def communicate(self):
            return (progress, b"")

        def kill(self):
            self.blocked = False
            self.returncode = -9

    destination = tmp_path / "pulled.mp4"
    adb = AdbBackend(
        serial="A", runner=run, popen=NoisyProcess,
        which=lambda name: "/bin/adb", timeout=0.05,
    )
    started = time.monotonic()
    assert adb.pull("clip.mp4", destination, max_bytes=32) is True
    assert time.monotonic() - started < 0.5
    assert destination.read_bytes() == b"valid-media"


@pytest.mark.parametrize("mode", ["failure", "timeout"])
def test_adb_pull_failure_and_timeout_remove_partial_destination(tmp_path, mode):
    def run(argv, **kwargs):
        return Result("List of devices attached\nA\tdevice product:x\n")

    class BrokenProcess:
        def __init__(self, argv, **kwargs):
            self.returncode = 1 if mode == "failure" else None
            Path(argv[-1]).write_bytes(b"partial")

        def poll(self):
            return self.returncode

        def communicate(self):
            return (b"", b"failed")

        def kill(self):
            self.returncode = -9

    destination = tmp_path / "partial.mp4"
    adb = AdbBackend(
        serial="A", runner=run, popen=BrokenProcess,
        which=lambda name: "/bin/adb", timeout=0.03,
    )
    assert adb.pull("clip.mp4", destination, max_bytes=32) is False
    assert not destination.exists()


@pytest.mark.parametrize("stdout,serial,available", [
    ("List of devices attached\n", None, False),
    ("List of devices attached\nA\tunauthorized\n", "A", False),
    ("List of devices attached\nA\tno permissions\n", "A", False),
])
def test_adb_unavailable_states_are_truthful(stdout, serial, available):
    adb = AdbBackend(serial=serial, runner=lambda argv, **kw: Result(stdout), which=lambda name: "/bin/adb")
    assert adb.available().available is available


@pytest.mark.parametrize("failure", [PermissionError("denied"), TimeoutError("timed out")])
def test_adb_permission_and_timeout_failures_are_truthful(failure):
    def run(argv, **kwargs):
        raise failure

    adb = AdbBackend(runner=run, which=lambda name: "/bin/adb")
    status = adb.available()
    assert status.available is False
    assert str(failure) in status.reason
    assert adb.push(Path("/does/not/matter"), "user-safe.mp4") is False


@pytest.mark.asyncio
async def test_job_rejects_oversized_converted_output_and_cleans_tempdir(tmp_path):
    class ExpandingTools(FakeTools):
        def convert(self, source, destination, plan=None, max_bytes=None):
            self.convert_calls.append((Path(source), Path(destination), plan, max_bytes))
            Path(destination).write_bytes(b"12345")
            return Path(destination)

    adb = FakeAdb()
    job = MediaJob(
        tmp_path, ExpandingTools(), adb, lambda: MediaCatalog(),
        max_bytes=4, idle_timeout=0.1,
    )
    with pytest.raises(ValueError, match="converted media exceeds size limit"):
        await job.run(Stream([b"x"]), "x.mp4")
    assert adb.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_cancellation_waits_for_background_converter_before_cleanup(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class BlockingTools(FakeTools):
        def convert(self, source, destination, plan=None, max_bytes=None):
            started.set()
            release.wait(2)
            Path(destination).write_bytes(b"converted")
            return Path(destination)

    job = MediaJob(
        tmp_path, BlockingTools(), FakeAdb(), lambda: MediaCatalog(),
        idle_timeout=0.1,
    )
    task = asyncio.create_task(job.run(Stream([b"x"]), "x.mp4"))
    assert await asyncio.get_running_loop().run_in_executor(None, started.wait, 1)
    task.cancel()
    await asyncio.sleep(0.02)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_preview_is_authorized_by_exact_conn_catalog_and_cleans_tempdir(tmp_path):
    class PreviewAdb(FakeAdb):
        def __init__(self):
            super().__init__()
            self.pull_calls = []

        def pull(self, name, destination, *, factory=False, max_bytes=None):
            self.pull_calls.append((name, Path(destination), factory, max_bytes))
            Path(destination).write_bytes(b"device-media")
            return True

    class PreviewTools(FakeTools):
        def thumbnail(self, source, destination, **kwargs):
            Path(destination).write_bytes(b"jpeg-preview")
            return Path(destination)

        def proxy(self, source, destination, **kwargs):
            Path(destination).write_bytes(b"mp4-proxy")
            return Path(destination)

    adb = PreviewAdb()
    catalog = MediaCatalog(("MiKu.PNG",), ("custom.mp4",))
    manager = MediaManager(
        tmp_path, PreviewTools(), adb, object(), lambda: catalog,
        max_bytes=32, max_concurrent_jobs=2,
    )
    thumbnail = await manager.preview("MiKu.PNG", "thumbnail")
    proxy = await manager.preview("custom.mp4", "proxy")
    assert thumbnail.data == b"jpeg-preview" and thumbnail.content_type == "image/jpeg"
    assert proxy.data == b"mp4-proxy" and proxy.content_type == "video/mp4"
    assert adb.pull_calls[0][2] is True and adb.pull_calls[1][2] is False
    with pytest.raises(FileNotFoundError):
        await manager.preview("miku.png", "thumbnail")
    with pytest.raises(ValueError):
        await manager.preview("../custom.mp4", "proxy")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_media_manager_bounds_active_jobs_and_terminal_result_retention(tmp_path):
    class GateStream:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def read(self, size):
            self.started.set()
            await self.release.wait()
            return b""

    adb = FakeAdb()
    manager = MediaManager(
        tmp_path, FakeTools(), adb, object(), lambda: MediaCatalog(),
        max_bytes=32, max_concurrent_jobs=2, max_results=2,
    )
    streams = [GateStream(), GateStream()]
    tasks = [asyncio.create_task(manager.upload(stream, "x.mp4")) for stream in streams]
    await asyncio.gather(*(stream.started.wait() for stream in streams))
    assert len(list(tmp_path.iterdir())) == 2
    with pytest.raises(MediaBusy):
        await manager.upload(Stream([b"x"]), "busy.mp4")
    assert len(list(tmp_path.iterdir())) == 2
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    assert list(tmp_path.iterdir()) == []

    custom = []

    def refresh():
        custom.append(adb.calls[-1][1])
        return MediaCatalog((), tuple(custom))

    manager.catalog_loader = refresh
    manager._refresh_conn_catalog = refresh
    results = [await manager.upload(Stream([b"x"]), "x.mp4") for _ in range(3)]
    assert len(manager.jobs) == 2
    assert results[0].job_id not in manager.jobs
    assert list(manager.jobs) == [results[1].job_id, results[2].job_id]


@pytest.mark.asyncio
async def test_upload_never_retargets_after_a_second_cooler_replaces_the_first(tmp_path, monkeypatch):
    from ryuo_screen import media

    usb = tmp_path / "usb"
    port = usb / "1-3"
    port.mkdir(parents=True)
    (port / "idVendor").write_text("0b05")
    (port / "idProduct").write_text("1c76")
    serial = port / "serial"
    serial.write_text("FIRST")
    monkeypatch.setattr(media, "USB_DEVICES", usb)
    pushes = []

    def run(argv, **kwargs):
        if argv[1:] == ["devices", "-l"]:
            current = serial.read_text()
            transport = "7" if current == "FIRST" else "9"
            return Result("List of devices attached\n{} device usb:1-3 transport_id:{}\n".format(current, transport))
        pushes.append(argv)
        return Result()

    class ReconnectDuringUpload(Stream):
        async def read(self, size):
            serial.write_text("SECOND")
            return await super().read(size)

    backend = AdbBackend(runner=run, which=lambda _: "adb")
    job = MediaJob(tmp_path / "jobs", FakeTools(), backend, lambda: MediaCatalog())
    result = await job.run(ReconnectDuringUpload([b"media"]))
    assert not result.applied
    assert pushes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("observer", ["status", "push"])
async def test_upload_binding_expires_at_any_observed_disconnect(tmp_path, monkeypatch, observer):
    connected = True
    pushes = []

    def run(argv, **kwargs):
        if argv[1:] == ["devices", "-l"]:
            row = "A device usb:1-3 transport_id:7" if connected else ""
            return Result("List of devices attached\n" + row)
        pushes.append(argv)
        return Result(returncode=1)

    monkeypatch.setattr("ryuo_screen.media._cooler_usb_identity", lambda: ("1-3", "A"))
    adb = AdbBackend(runner=run, which=lambda _: "stub-adb")
    manager = MediaManager(tmp_path, FakeTools(), adb, object(), lambda: MediaCatalog())
    _, token = await manager.adb_status()
    assert token

    class DisconnectAfterAdmission(Stream):
        async def read(self, size):
            nonlocal connected
            if self.chunks:
                connected = False
                if observer == "status":
                    absent, _ = await manager.adb_status()
                    assert not absent.available
                    connected = True
                    _, new_token = await manager.adb_status()
                    assert new_token and new_token != token
            return await super().read(size)

    result = await manager.upload(DisconnectAfterAdmission([b"media"]), "image", token)
    assert not result.applied and not result.confirmed
    assert pushes == []
    connected = True
    with pytest.raises(MediaTargetChanged):
        await manager.upload(Stream([b"media"]), "image", token)
    assert pushes == []
