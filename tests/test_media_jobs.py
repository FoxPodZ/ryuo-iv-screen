# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import threading
from pathlib import Path

import pytest

from ryuo_screen.media import AdbBackend, MediaCatalog, MediaInfo, MediaJob, MediaTools


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

    def push(self, source, name):
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
