# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded media inspection, conversion and ADB delivery.

Client supplied names are descriptive only.  They are never used as a local
path, remote path, or subprocess argument; every uploaded asset receives a
generated basename under ``/sdcard/pcMedia``.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import asynccontextmanager, nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

import ryuo_proto as proto

from .device import DeviceCommand
from .models import CommandResult


USB_DEVICES = Path("/sys/bus/usb/devices")
REMOTE_MEDIA_DIR = "/sdcard/pcMedia"
REMOTE_FACTORY_MEDIA_DIR = "/sdcard/pcMediaPreset"
MAX_THUMBNAIL = (640, 360)
MAX_PROXY = (1280, 720)
MAX_THUMBNAIL_BYTES = 8 * 1024 * 1024
MAX_PROXY_BYTES = 64 * 1024 * 1024
MAX_PROXY_SECONDS = 30


class ToolUnavailable(RuntimeError):
    """A required external media tool is not installed."""


class MediaBusy(RuntimeError):
    """The bounded media worker capacity is already in use."""


class MediaTargetChanged(RuntimeError):
    """The upload does not match the physical target shown in media status."""


class MediaOperationError(RuntimeError):
    """A bounded external media operation failed."""


@dataclass(frozen=True)
class MediaCatalog:
    factory: Tuple[str, ...] = ()
    custom: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "factory", self._names("factory", self.factory))
        object.__setattr__(self, "custom", self._names("custom", self.custom))

    @staticmethod
    def _names(label: str, values: Sequence[str]) -> Tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise TypeError("{} media list must be a sequence".format(label))
        result = []
        for value in values:
            if not isinstance(value, str):
                raise TypeError("{} media names must be strings".format(label))
            result.append(value)
        return tuple(result)

    @classmethod
    def from_conn(cls, descriptor: Mapping[str, Any]) -> "MediaCatalog":
        if not isinstance(descriptor, Mapping):
            raise TypeError("conn descriptor must be an object")
        media = descriptor.get("media") or {}
        if not isinstance(media, Mapping):
            raise TypeError("conn media listing must be an object")
        return cls(media.get("preset") or (), media.get("custom") or ())

    def classify(self, name: str) -> Optional[str]:
        if name in self.factory:
            return "factory"
        if name in self.custom:
            return "custom"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"factory": list(self.factory), "custom": list(self.custom)}


@dataclass(frozen=True)
class MediaInfo:
    name: str
    container: str
    codec: str
    pixel_format: Optional[str]
    width: int
    height: int
    duration: Optional[float]
    size: int


@dataclass(frozen=True)
class ConversionPlan:
    action: str
    suffix: str

    def __post_init__(self) -> None:
        if self.action not in ("passthrough", "transcode-video", "convert-still"):
            raise ValueError("unsupported conversion action")
        if self.suffix not in (".mp4", ".png"):
            raise ValueError("unsupported media suffix")


class MediaTools:
    """Explicit-argv wrappers around ffprobe and ffmpeg."""

    def __init__(
        self,
        ffprobe: str = "ffprobe",
        ffmpeg: str = "ffmpeg",
        runner: Callable[..., Any] = subprocess.run,
        which: Callable[[str], Optional[str]] = shutil.which,
        timeout: float = 120.0,
    ) -> None:
        self._ffprobe_name = ffprobe
        self._ffmpeg_name = ffmpeg
        self._runner = runner
        self._which = which
        self._timeout = float(timeout)

    def status(self) -> Dict[str, bool]:
        return {
            "ffprobe": self._which(self._ffprobe_name) is not None,
            "ffmpeg": self._which(self._ffmpeg_name) is not None,
        }

    def _tool(self, name: str) -> str:
        value = self._which(name)
        if not value:
            raise ToolUnavailable("{} is not installed".format(name))
        return value

    def _run(self, argv: Sequence[str], *, capture: bool = False) -> Any:
        kwargs: Dict[str, Any] = {"timeout": self._timeout}
        if capture:
            kwargs.update({"capture_output": True, "text": True})
        result = self._runner(list(argv), **kwargs)
        if getattr(result, "returncode", 0) != 0:
            raise RuntimeError(
                "media tool failed: {}".format(getattr(result, "stderr", "unknown error"))
            )
        return result

    def probe(self, path: Path) -> MediaInfo:
        tool = self._tool(self._ffprobe_name)
        result = self._run([
            tool, "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(Path(path)),
        ], capture=True)
        try:
            document = json.loads(result.stdout)
            streams = document.get("streams") or []
            video = next(item for item in streams if item.get("codec_type") == "video")
            fmt = document.get("format") or {}
            duration = fmt.get("duration")
            size = fmt.get("size")
            return MediaInfo(
                Path(str(fmt.get("filename") or path)).name,
                str(fmt.get("format_name") or "unknown"),
                str(video.get("codec_name") or "unknown").lower(),
                (str(video["pix_fmt"]).lower() if video.get("pix_fmt") else None),
                int(video.get("width") or 0),
                int(video.get("height") or 0),
                (float(duration) if duration not in (None, "N/A") else None),
                int(size or 0),
            )
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("ffprobe returned no usable video stream") from exc

    def plan(self, info: MediaInfo) -> ConversionPlan:
        codec = info.codec.lower()
        containers = {
            item.strip().lower() for item in info.container.split(",") if item.strip()
        }
        is_still = codec in ("png", "mjpeg", "jpeg")
        is_gif = codec == "gif" and "gif" in containers
        is_mp4 = bool(containers.intersection(("mov", "mp4")))
        is_image = is_still and bool(
            containers.intersection(("image2", "png_pipe", "jpeg_pipe", "mjpeg"))
        )
        if not (is_mp4 or is_gif or is_image):
            raise ValueError("unsupported media format; use MP4, GIF, PNG, or JPG")
        if is_image and codec == "png" and info.width == 2240 and info.height == 1080:
            return ConversionPlan("passthrough", ".png")
        if is_still:
            return ConversionPlan("convert-still", ".png")
        if (
            codec in ("hevc", "h265")
            and (info.pixel_format or "").lower() == "yuv420p"
            and info.width == 2240
            and info.height == 1080
        ):
            return ConversionPlan("passthrough", ".mp4")
        return ConversionPlan("transcode-video", ".mp4")

    def convert(
        self, source: Path, destination: Path,
        plan: Optional[ConversionPlan] = None,
        max_bytes: Optional[int] = None,
    ) -> Path:
        source = Path(source)
        destination = Path(destination)
        plan = plan or self.plan(self.probe(source))
        if plan.action == "passthrough":
            shutil.copy2(str(source), str(destination))
            return destination
        tool = self._tool(self._ffmpeg_name)
        if max_bytes is not None:
            if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
                raise ValueError("conversion byte limit must be a positive integer")
        scale = "scale=2240:1080:force_original_aspect_ratio=increase:flags=lanczos,setsar=1,crop=2240:1080"
        argv = [tool, "-nostdin", "-y", "-i", str(source), "-vf", scale]
        if plan.action == "convert-still":
            argv.extend(["-frames:v", "1", "-an"])
        else:
            argv.extend([
                "-c:v", "libx265", "-tag:v", "hvc1", "-pix_fmt", "yuv420p",
                "-crf", "24", "-maxrate", "8M", "-bufsize", "16M",
                "-movflags", "+faststart", "-threads", "2", "-x265-params",
                "pools=2:frame-threads=2:log-level=error", "-an",
            ])
        if max_bytes is not None:
            argv.extend(["-fs", str(max_bytes)])
        argv.append(str(destination))
        self._run(argv)
        return destination

    def thumbnail(self, source: Path, destination: Path, *, width: int = 320, height: int = 180) -> Path:
        self._bounded(width, height, MAX_THUMBNAIL, "thumbnail")
        tool = self._tool(self._ffmpeg_name)
        self._run([
            tool, "-nostdin", "-y", "-i", str(Path(source)), "-frames:v", "1",
            "-vf", "scale={}:{}".format(width, height),
            "-fs", str(MAX_THUMBNAIL_BYTES), str(Path(destination)),
        ])
        return Path(destination)

    def proxy(self, source: Path, destination: Path, *, width: int = 960, height: int = 540) -> Path:
        self._bounded(width, height, MAX_PROXY, "proxy")
        tool = self._tool(self._ffmpeg_name)
        self._run([
            tool, "-nostdin", "-y", "-i", str(Path(source)),
            "-vf", "scale={}:{}".format(width, height), "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
            "-t", str(MAX_PROXY_SECONDS), "-fs", str(MAX_PROXY_BYTES),
            str(Path(destination)),
        ])
        return Path(destination)

    @staticmethod
    def _bounded(width: int, height: int, maximum: Tuple[int, int], label: str) -> None:
        if (
            isinstance(width, bool) or not isinstance(width, int)
            or isinstance(height, bool) or not isinstance(height, int)
            or width <= 0 or height <= 0 or width > maximum[0] or height > maximum[1]
        ):
            raise ValueError("{} dimensions exceed the bounded preview size".format(label))


@dataclass(frozen=True)
class AdbAvailability:
    available: bool
    reason: Optional[str] = None
    serial: Optional[str] = None
    transport_id: Optional[str] = None
    usb_port: Optional[str] = None
    target_token: Optional[str] = None

    def target_args(self) -> Tuple[str, str]:
        if self.transport_id is not None:
            return "-t", self.transport_id
        if self.serial is None:
            raise ValueError("no ADB target selected")
        return "-s", self.serial


def _cooler_usb_identity() -> Optional[Tuple[str, str]]:
    """Return the unique Ryuo USB port and serial visible to the daemon."""
    identities = []
    try:
        for node in USB_DEVICES.iterdir():
            if not re.fullmatch(r"[0-9]+-[0-9]+(?:\.[0-9]+)*", node.name):
                continue
            vendor = int((node / "idVendor").read_text("ascii").strip(), 16)
            if vendor not in proto.VIDS:
                continue
            product = int((node / "idProduct").read_text("ascii").strip(), 16)
            if product == proto.PID:
                serial = (node / "serial").read_text("utf-8").strip()
                if not serial:
                    return None
                identities.append((node.name, serial))
    except (OSError, ValueError):
        return None
    return identities[0] if len(identities) == 1 else None


class AdbBackend:
    def __init__(
        self, serial: Optional[str] = None, adb: str = "adb",
        runner: Callable[..., Any] = subprocess.run,
        popen: Callable[..., Any] = subprocess.Popen,
        which: Callable[[str], Optional[str]] = shutil.which,
        timeout: float = 120.0,
    ) -> None:
        self.serial = serial
        self._adb_name = adb
        self._runner = runner
        self._popen = popen
        self._which = which
        self._timeout = float(timeout)
        self._target_lock = threading.RLock()
        self._last_target: Optional[AdbAvailability] = None
        self._target_token: Optional[str] = None

    def _tool(self) -> Optional[str]:
        return self._which(self._adb_name)

    def available(self) -> AdbAvailability:
        # Push, pull and status observations all advance the same generation.
        with self._target_lock:
            target = self._discover()
            if target != self._last_target:
                self._last_target = target
                self._target_token = uuid.uuid4().hex if target.transport_id else None
            return replace(target, target_token=self._target_token)

    def _discover(self) -> AdbAvailability:
        tool = self._tool()
        if not tool:
            return AdbAvailability(False, "adb is not installed")
        try:
            result = self._runner(
                [tool, "devices", "-l"], capture_output=True, text=True,
                timeout=min(self._timeout, 10.0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return AdbAvailability(False, str(exc) or exc.__class__.__name__, self.serial)
        if getattr(result, "returncode", 0) != 0:
            return AdbAvailability(False, getattr(result, "stderr", "adb failed"))
        devices = [line.split() for line in str(result.stdout).splitlines()[1:] if line.strip()]
        if self.serial is not None:
            matches = [parts for parts in devices if parts[0] == self.serial]
            if len(matches) != 1 or matches[0][1:2] != ["device"]:
                return AdbAvailability(False, "selected ADB device is unavailable", self.serial)
            return AdbAvailability(True, serial=self.serial)

        physical = [parts for parts in devices if parts[1:2] == ["device"]
                    and any(field.startswith("usb:") for field in parts[2:])]
        identity = _cooler_usb_identity() if physical else None
        if identity is not None:
            port, serial = identity
            matches = [
                parts for parts in physical
                if parts[0] == serial and "usb:" + port in parts[2:]
            ]
            if len(matches) == 1:
                ids = [field.partition(":")[2] for field in matches[0][2:]
                       if field.startswith("transport_id:")]
                if len(ids) == 1 and re.fullmatch(r"[1-9][0-9]*", ids[0]):
                    return AdbAvailability(True, serial=serial, transport_id=ids[0], usb_port=port)
        return AdbAvailability(False, "cannot identify the Ryuo USB transport; configure ANDROID_SERIAL")

    def push(
        self, source: Path, name: str, *, target: Optional[AdbAvailability] = None,
    ) -> bool:
        proto.check_media_name(name)
        # Serialize observations with automatic dispatch so status cannot
        # revoke the generation between the final check and the command.
        with self._target_lock if self.serial is None else nullcontext():
            availability = self.available()
            if target is not None and availability != target:
                return False
            if not availability.available or availability.serial is None:
                return False
            tool = self._tool()
            assert tool is not None
            try:
                result = self._runner([
                    tool, *availability.target_args(), "push", str(Path(source)),
                    REMOTE_MEDIA_DIR + "/" + name,
                ], capture_output=True, text=True, timeout=self._timeout)
            except (OSError, subprocess.SubprocessError):
                return False
            return getattr(result, "returncode", 0) == 0

    def pull(
        self, name: str, destination: Path, *, factory: bool = False,
        max_bytes: int = 256 * 1024 * 1024,
    ) -> bool:
        proto.check_media_name(name)
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("ADB pull byte limit must be a positive integer")
        availability = self.available()
        if not availability.available or availability.serial is None:
            return False
        tool = self._tool()
        assert tool is not None
        destination = Path(destination)
        remote_root = REMOTE_FACTORY_MEDIA_DIR if factory else REMOTE_MEDIA_DIR
        argv = [
            tool, *availability.target_args(), "pull",
            remote_root + "/" + name, str(destination),
        ]
        process = None
        deadline = time.monotonic() + self._timeout
        try:
            process = self._popen(
                # adb progress/error text is not part of the API contract.
                # Discard it so a verbose transfer cannot fill an unread pipe
                # while this loop monitors timeout and destination size.
                argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            while process.poll() is None:
                if destination.exists() and destination.stat().st_size > max_bytes:
                    process.kill()
                    process.communicate()
                    destination.unlink()
                    return False
                if time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    if destination.exists():
                        destination.unlink()
                    return False
                time.sleep(0.02)
            process.communicate()
        except (OSError, subprocess.SubprocessError):
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()
            if destination.exists():
                destination.unlink()
            return False
        if (
            getattr(process, "returncode", 1) != 0
            or not destination.is_file()
            or destination.stat().st_size > max_bytes
        ):
            if destination.exists():
                destination.unlink()
            return False
        return True


@dataclass(frozen=True)
class MediaJobResult:
    job_id: str
    name: Optional[str]
    applied: bool
    confirmed: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jobId": self.job_id, "name": self.name, "applied": self.applied,
            "confirmed": self.confirmed, "error": self.error,
        }


@dataclass(frozen=True)
class MediaPreview:
    data: bytes
    content_type: str


async def _call_sync(
    function: Callable[..., Any], *args: Any, executor: Optional[Executor] = None, **kwargs: Any,
) -> Any:
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(executor, lambda: function(*args, **kwargs))
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        # The executor call cannot be killed safely.  Delay cancellation until
        # it has stopped touching per-job files, then let the caller's finally
        # remove the directory without racing ffmpeg/adb.
        while not future.done():
            try:
                await asyncio.shield(future)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        raise


async def _call_adb(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    # Each admitted job can issue one ADB call at a time, plus one shared
    # status probe. Retire each worker as soon as its one command finishes.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ryuo-adb") as worker:
        return await _call_sync(function, *args, executor=worker, **kwargs)


class MediaJob:
    def __init__(
        self, temp_root: Path, tools: MediaTools, adb: AdbBackend,
        refresh_catalog: Callable[[], Any], *, max_bytes: int = 256 * 1024 * 1024,
        idle_timeout: float = 30.0, chunk_size: int = 256 * 1024,
    ) -> None:
        if max_bytes <= 0 or idle_timeout <= 0 or chunk_size <= 0:
            raise ValueError("media job limits must be positive")
        self.temp_root = Path(temp_root)
        self.tools = tools
        self.adb = adb
        self.refresh_catalog = refresh_catalog
        self.max_bytes = int(max_bytes)
        self.idle_timeout = float(idle_timeout)
        self.chunk_size = int(chunk_size)
        self.job_id = uuid.uuid4().hex

    async def run(
        self, stream: Any, original_name: str = "upload", *,
        target: Optional[AdbAvailability] = None,
    ) -> MediaJobResult:
        # original_name is deliberately never used in a path or command.
        del original_name
        if target is None:
            target = await _call_adb(self.adb.available)
        if not target.available:
            return MediaJobResult(self.job_id, None, False, False, target.reason)
        self.temp_root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="job-", dir=str(self.temp_root)))
        source = directory / "source.upload"
        try:
            total = 0
            with source.open("wb") as handle:
                while True:
                    chunk = await asyncio.wait_for(
                        stream.read(self.chunk_size), timeout=self.idle_timeout
                    )
                    if not chunk:
                        break
                    if not isinstance(chunk, (bytes, bytearray)):
                        raise TypeError("upload stream must return bytes")
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise ValueError("upload exceeds size limit")
                    handle.write(chunk)
            if total == 0:
                raise ValueError("upload is empty")
            info = await _call_sync(self.tools.probe, source)
            plan = self.tools.plan(info)
            name = "user-{}{}".format(uuid.uuid4().hex, plan.suffix)
            output = directory / ("converted" + plan.suffix)
            if plan.action == "passthrough":
                await _call_sync(shutil.copy2, str(source), str(output))
            else:
                await _call_sync(self.tools.convert, source, output, plan, self.max_bytes)
            if output.stat().st_size > self.max_bytes:
                raise ValueError("converted media exceeds size limit")
            pushed = await _call_adb(self.adb.push, output, name, target=target)
            if not pushed:
                return MediaJobResult(self.job_id, name, False, False, "ADB push failed")
            refreshed = self.refresh_catalog()
            if inspect.isawaitable(refreshed):
                refreshed = await refreshed
            if not isinstance(refreshed, MediaCatalog):
                raise TypeError("catalog refresh must return MediaCatalog")
            confirmed = name in refreshed.custom
            return MediaJobResult(
                self.job_id, name, confirmed, confirmed,
                None if confirmed else "uploaded file was not present in refreshed conn listing",
            )
        finally:
            shutil.rmtree(str(directory), ignore_errors=True)


class MediaManager:
    def __init__(
        self, temp_root: Path, tools: MediaTools, adb: AdbBackend, device: Any,
        catalog_loader: Callable[[], MediaCatalog], *,
        max_bytes: int = 256 * 1024 * 1024, idle_timeout: float = 30.0,
        refresh_timeout: float = 10.0,
        max_concurrent_jobs: int = 2, max_results: int = 128,
    ) -> None:
        self.temp_root = Path(temp_root)
        self.tools = tools
        self.adb = adb
        self.device = device
        self.catalog_loader = catalog_loader
        self.max_bytes = max_bytes
        self.idle_timeout = idle_timeout
        self.refresh_timeout = float(refresh_timeout)
        if (
            self.refresh_timeout <= 0
            or isinstance(max_concurrent_jobs, bool)
            or not isinstance(max_concurrent_jobs, int)
            or max_concurrent_jobs <= 0
            or isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results <= 0
        ):
            raise ValueError("media refresh and capacity limits must be positive")
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_results = max_results
        self._active_jobs = 0
        self._status_probe: Optional[asyncio.Task] = None
        self.jobs: "OrderedDict[str, MediaJobResult]" = OrderedDict()

    def catalog(self) -> MediaCatalog:
        value = self.catalog_loader()
        if not isinstance(value, MediaCatalog):
            raise TypeError("catalog loader must return MediaCatalog")
        return value

    async def adb_status(self) -> Tuple[AdbAvailability, Optional[str]]:
        if self._status_probe is None or self._status_probe.done():
            self._status_probe = asyncio.create_task(_call_adb(self.adb.available))
        target = await asyncio.shield(self._status_probe)
        return target, target.target_token

    @asynccontextmanager
    async def _admit(self):
        # All API calls enter on one event loop.  No await between the check
        # and increment makes admission deterministic and avoids an unbounded
        # queue of requests waiting behind the media tools.
        if self._active_jobs >= self.max_concurrent_jobs:
            raise MediaBusy("media job capacity is full")
        self._active_jobs += 1
        try:
            yield
        finally:
            self._active_jobs -= 1

    def _remember(self, result: MediaJobResult) -> None:
        self.jobs.pop(result.job_id, None)
        self.jobs[result.job_id] = result
        while len(self.jobs) > self.max_results:
            self.jobs.popitem(last=False)

    async def upload(
        self, stream: Any, original_name: str, target_token: Optional[str] = None,
    ) -> MediaJobResult:
        async with self._admit():
            target = await _call_adb(self.adb.available)
            if target_token != target.target_token:
                raise MediaTargetChanged("refresh media status and confirm the current ADB target")
            job = MediaJob(
                self.temp_root, self.tools, self.adb, self._refresh_conn_catalog,
                max_bytes=self.max_bytes, idle_timeout=self.idle_timeout,
            )
            result = await job.run(stream, original_name, target=target)
            self._remember(result)
            return result

    async def preview(self, name: str, kind: str) -> MediaPreview:
        proto.check_media_name(name)
        catalog = self.catalog()
        classification = catalog.classify(name)
        if classification is None:
            raise FileNotFoundError(name)
        if kind not in ("thumbnail", "proxy"):
            raise ValueError("preview kind must be thumbnail or proxy")
        async with self._admit():
            self.temp_root.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="preview-", dir=str(self.temp_root)))
            source = directory / "source.media"
            destination = directory / ("thumbnail.jpg" if kind == "thumbnail" else "proxy.mp4")
            try:
                pulled = await _call_adb(
                    self.adb.pull, name, source,
                    factory=classification == "factory", max_bytes=self.max_bytes,
                )
                if not pulled:
                    raise MediaOperationError("ADB media pull failed")
                if kind == "thumbnail":
                    await _call_sync(self.tools.thumbnail, source, destination)
                    content_type = "image/jpeg"
                else:
                    await _call_sync(self.tools.proxy, source, destination)
                    content_type = "video/mp4"
                return MediaPreview(destination.read_bytes(), content_type)
            finally:
                shutil.rmtree(str(directory), ignore_errors=True)

    async def delete(self, name: str) -> MediaJobResult:
        proto.check_media_name(name)
        before = self.catalog()
        if name in before.factory:
            raise PermissionError("factory media cannot be deleted")
        if name not in before.custom:
            raise FileNotFoundError(name)
        async with self._admit():
            command = DeviceCommand(
                proto.POST, proto.RES_MEDIA_DELETE,
                proto.media_delete_payload(include=[name]), priority=20,
                coalesce_key="media-delete:{}".format(name),
                expect_reply=True,
            )
            ticket = self.device.submit(command)
            if hasattr(ticket, "wait"):
                result = await _call_sync(ticket.wait, 10.0)
            elif hasattr(ticket, "snapshot"):
                result = ticket.snapshot()
            else:
                raise TypeError("device submit must return a command ticket")
            if not isinstance(result, CommandResult):
                raise TypeError("device command returned an invalid result")
            refreshed = await self._refresh_conn_catalog()
            confirmed = bool(result.applied and result.acked and name not in refreshed.custom)
            job_result = MediaJobResult(
                uuid.uuid4().hex, name, confirmed, confirmed,
                None if confirmed else result.error or "delete was not confirmed by refreshed conn listing",
            )
            self._remember(job_result)
            return job_result

    async def _refresh_conn_catalog(self) -> MediaCatalog:
        """Force a new ``conn`` handshake when the worker supports it.

        The descriptor remains the only classification authority.  ADB output
        is never promoted into factory/custom state.
        """
        notifier = getattr(self.device, "notify_resume", None)
        if not callable(notifier):
            return self.catalog()
        before = getattr(self.device.status(), "recovery_count", None)
        notifier()
        deadline = asyncio.get_running_loop().time() + self.refresh_timeout
        while True:
            status = self.device.status()
            recovery = getattr(status, "recovery_count", None)
            if before is None or (recovery is not None and recovery > before):
                return self.catalog()
            if asyncio.get_running_loop().time() >= deadline:
                return self.catalog()
            await asyncio.sleep(0.05)


__all__ = [
    "AdbAvailability", "AdbBackend", "ConversionPlan", "MediaCatalog",
    "MediaBusy", "MediaInfo", "MediaJob", "MediaJobResult", "MediaManager",
    "MediaOperationError", "MediaPreview", "MediaTools", "ToolUnavailable",
]
