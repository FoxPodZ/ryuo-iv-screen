# SPDX-License-Identifier: GPL-3.0-or-later
"""aiohttp TCP and Unix-domain socket lifecycle helpers."""

from __future__ import annotations

import errno
import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

from aiohttp import web

from .auth import SECURITY_KEY, SecurityPolicy


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


__all__ = ["DEFAULT_TCP", "DEFAULT_UDS", "RunningSites", "run_sites"]
