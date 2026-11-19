# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the Ryuo screen device worker and its HTTP and Unix-socket API."""

from __future__ import annotations

import argparse
import asyncio
import errno
import os
import signal
import socket
import stat
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

from aiohttp import web

from .api import AppContext, create_app
from .auth import SECURITY_KEY, SecurityPolicy
from .device import DeviceWorker, HidTransport
from .media import AdbBackend, MediaCatalog, MediaManager, MediaTools
from .store import AppConfig, ProfileStore, StateStore
from .telemetry.amd import AmdGpuProvider
from .telemetry.collector import TelemetryCollector
from .telemetry.cpu import CpuProvider
from .telemetry.hwmon import HwmonProvider
from .telemetry.nvidia import NvidiaProvider
from .telemetry.sysfs import Sysfs


DEFAULT_TCP = ("127.0.0.1", 8746)
DEFAULT_UDS = Path("/run/ryuo-screen/control.sock")


def _prepare_socket(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(metadata.st_mode):
        raise FileExistsError("refusing to replace non-socket path {}".format(path))
    if metadata.st_uid != os.geteuid():
        raise PermissionError("refusing to replace socket owned by another user")
    identity = (metadata.st_dev, metadata.st_ino)
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(0.1)
    try:
        probe.connect(str(path))
    except OSError as exc:
        if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
            raise FileExistsError(
                "refusing to replace Unix socket with unknown listener state"
            ) from exc
    else:
        raise FileExistsError("refusing to replace active Unix socket {}".format(path))
    finally:
        probe.close()
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if (
        (current.st_dev, current.st_ino) != identity
        or not stat.S_ISSOCK(current.st_mode)
        or current.st_uid != os.geteuid()
    ):
        raise FileExistsError("Unix socket changed while checking stale state")
    path.unlink()


@dataclass
class RunningSites:
    runner: web.AppRunner
    tcp_site: Optional[web.TCPSite]
    unix_site: Optional[web.UnixSite]
    socket_path: Optional[Path]
    socket_identity: Optional[Tuple[int, int]]
    tcp_address: Optional[Tuple[str, int]]
    _stopped: bool = False

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            await self.runner.cleanup()
        finally:
            path = self.socket_path
            identity = self.socket_identity
            if path is not None and identity is not None:
                try:
                    metadata = path.lstat()
                except FileNotFoundError:
                    pass
                else:
                    current = (metadata.st_dev, metadata.st_ino)
                    if current == identity and stat.S_ISSOCK(metadata.st_mode):
                        path.unlink()


async def run_sites(
    app: web.Application,
    tcp: Optional[Tuple[str, int]] = DEFAULT_TCP,
    uds: Optional[Union[str, Path]] = DEFAULT_UDS,
    security: Optional[SecurityPolicy] = None,
) -> RunningSites:
    """Start one aiohttp application on TCP and/or a protected Unix socket."""
    if not isinstance(app, web.Application):
        raise TypeError("app must be an aiohttp Application")
    if tcp is None and uds is None:
        raise ValueError("at least one API site is required")
    app_policy = app.get(SECURITY_KEY)
    if security is not None and app_policy is not None and security is not app_policy:
        raise ValueError("security must match the application security policy")
    policy = app_policy if app_policy is not None else security
    if tcp is not None:
        host, _port = tcp
        if not host in ("localhost", "127.0.0.1", "::1") and app_policy is None:
            raise ValueError("LAN application requires installed security middleware")
        if policy is None:
            if host not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError("LAN bind requires an explicit security policy")
        else:
            if not isinstance(policy, SecurityPolicy):
                raise TypeError("security must be a SecurityPolicy")
            policy.validate_bind(host)
    socket_path = Path(uds) if uds is not None else None
    if socket_path is not None:
        socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        _prepare_socket(socket_path)

    runner = web.AppRunner(app)
    await runner.setup()
    tcp_site = None
    unix_site = None
    socket_identity = None
    tcp_address = None
    try:
        if tcp is not None:
            host, port = tcp
            tcp_site = web.TCPSite(runner, host, port)
            await tcp_site.start()
            server = getattr(tcp_site, "_server", None)
            sockets = getattr(server, "sockets", ())
            if sockets:
                bound = sockets[0].getsockname()
                tcp_address = (str(bound[0]), int(bound[1]))
            else:  # pragma: no cover - aiohttp always exposes sockets after start
                tcp_address = (host, port)
        if socket_path is not None:
            unix_site = web.UnixSite(runner, str(socket_path))
            await unix_site.start()
            os.chmod(str(socket_path), 0o660)
            metadata = socket_path.lstat()
            socket_identity = (metadata.st_dev, metadata.st_ino)
    except Exception:
        await runner.cleanup()
        if socket_path is not None:
            try:
                metadata = socket_path.lstat()
            except FileNotFoundError:
                pass
            else:
                if stat.S_ISSOCK(metadata.st_mode) and metadata.st_uid == os.geteuid():
                    socket_path.unlink()
        raise
    return RunningSites(
        runner, tcp_site, unix_site, socket_path, socket_identity, tcp_address
    )


async def serve(config: AppConfig, socket_path: Path, web_root: Optional[Path]) -> None:
    policy = SecurityPolicy.from_config(config)
    policy.validate_bind(config.listen_host)
    sysfs = Sysfs()
    preferred = config.gpu_provider if config.gpu_provider != "auto" else None
    collector = TelemetryCollector((
        CpuProvider(sysfs), HwmonProvider(sysfs, config.motherboard_sensor),
        AmdGpuProvider(sysfs, config.gpu_selector if preferred != "nvidia" else None),
        NvidiaProvider(config.gpu_selector if preferred != "amd" else None),
    ), preferred)
    state_store = StateStore(config.state_path)
    worker = DeviceWorker(HidTransport(), collector, state_store.load())
    media = MediaManager(
        Path("/var/cache/ryuo-screen"), MediaTools(), AdbBackend(serial=os.getenv("ANDROID_SERIAL")),
        worker, lambda: MediaCatalog.from_conn(worker.status().descriptor),
    )
    app = create_app(AppContext(
        state_store, ProfileStore(config.profiles_dir), worker, collector,
        media=media, security=policy, web_root=web_root,
    ))
    loop = asyncio.get_running_loop()
    shutdown = asyncio.Event()
    async with AsyncExitStack() as cleanup:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown.set)
            cleanup.callback(loop.remove_signal_handler, sig)
        worker.start()
        cleanup.callback(worker.stop)
        sites = await run_sites(app, (config.listen_host, config.listen_port), socket_path)
        cleanup.push_async_callback(sites.stop)
        await shutdown.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=AppConfig.config_path,
                        help="system TOML file (default: %(default)s)")
    parser.add_argument("--socket", type=Path, default=DEFAULT_UDS,
                        help="local control socket (default: %(default)s)")
    parser.add_argument("--web-root", type=Path,
                        help="directory containing the built Web UI (source checkout: web/dist)")
    args = parser.parse_args()
    asyncio.run(serve(AppConfig.load(args.config), args.socket, args.web_root))


__all__ = ["DEFAULT_TCP", "DEFAULT_UDS", "RunningSites", "run_sites", "serve", "main"]


if __name__ == "__main__":
    main()
