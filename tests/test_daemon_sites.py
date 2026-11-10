# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
import socket
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web

from ryuo_screen.daemon import DEFAULT_TCP, run_sites


def _app():
    app = web.Application()

    async def state(_request):
        return web.json_response({"revision": 7, "schema": "same"})

    app.router.add_get("/api/v1/state", state)
    return app


@pytest.mark.asyncio
async def test_tcp_and_uds_serve_same_schema_and_socket_is_cleaned(tmp_path):
    socket_path = tmp_path / "control.sock"
    sites = await run_sites(_app(), tcp=("127.0.0.1", 0), uds=socket_path)
    try:
        assert DEFAULT_TCP == ("127.0.0.1", 8746)
        assert socket_path.stat().st_mode & 0o777 == 0o660
        host, port = sites.tcp_address
        async with aiohttp.ClientSession() as session:
            tcp_body = await (
                await session.get("http://{}:{}/api/v1/state".format(host, port))
            ).json()
        connector = aiohttp.UnixConnector(path=str(socket_path))
        async with aiohttp.ClientSession(connector=connector) as session:
            uds_body = await (
                await session.get("http://localhost/api/v1/state")
            ).json()
        assert tcp_body == uds_body
    finally:
        await sites.stop()
    assert not socket_path.exists()


@pytest.mark.asyncio
async def test_stale_owned_socket_is_replaced_but_regular_file_is_refused(tmp_path):
    socket_path = tmp_path / "control.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(socket_path))
    stale.close()

    sites = await run_sites(_app(), tcp=None, uds=socket_path)
    await sites.stop()
    assert not socket_path.exists()

    socket_path.write_text("do not delete", encoding="utf-8")
    with pytest.raises(FileExistsError):
        await run_sites(_app(), tcp=None, uds=socket_path)
    assert socket_path.read_text(encoding="utf-8") == "do not delete"


@pytest.mark.asyncio
async def test_foreign_owned_socket_is_not_removed(tmp_path, monkeypatch):
    socket_path = tmp_path / "control.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(socket_path))
    stale.close()
    actual_uid = socket_path.stat().st_uid
    monkeypatch.setattr(os, "geteuid", lambda: actual_uid + 1)
    with pytest.raises(PermissionError):
        await run_sites(_app(), tcp=None, uds=socket_path)
    assert socket_path.exists()
