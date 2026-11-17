# SPDX-License-Identifier: GPL-3.0-or-later
import errno
import json
import socket
import socketserver
import tempfile
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest


@pytest.fixture
def unix_http():
    """Serve real HTTP over a short temporary Unix socket path."""
    if not hasattr(socketserver, "UnixStreamServer"):
        pytest.skip("filesystem Unix sockets are unavailable")
    calls = []
    responses = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_request(self):
            size = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(size)
            calls.append((self.command, self.path, json.loads(raw) if raw else None))
            assert self.headers["Host"] == "localhost"
            assert self.headers["Accept"] == "application/json"
            if raw:
                assert self.headers["Content-Type"] == "application/json"
            status, payload = responses.pop(0)
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(raw)
            except BrokenPipeError:
                pass

        do_GET = do_PATCH = do_DELETE = do_request

        def log_message(self, *_args):
            pass

    with tempfile.TemporaryDirectory(prefix="ryu-") as directory:
        path = Path(directory) / "control.sock"
        with socketserver.UnixStreamServer(str(path), Handler) as server:
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}
            )
            thread.start()
            try:
                yield path, calls, responses
            finally:
                server.shutdown()
                thread.join()


def test_requests_json_over_unix_socket(unix_http):
    from ryuo_screen.client import UnixApiClient

    path, calls, responses = unix_http
    responses.append((200, {"revision": 6, "queued": True}))
    result = UnixApiClient(path).request(
        "PATCH", "/api/v1/brightness", {"revision": 5, "brightness": 30}
    )
    assert result == {"revision": 6, "queued": True}
    assert calls == [("PATCH", "/api/v1/brightness", {"revision": 5, "brightness": 30})]


def test_missing_socket_is_unavailable(tmp_path):
    from ryuo_screen.client import ServiceUnavailable, UnixApiClient

    with pytest.raises(ServiceUnavailable):
        UnixApiClient(tmp_path / "missing").request("GET", "/api/v1/state")


def test_other_connect_errors_fail_closed(monkeypatch):
    from ryuo_screen.client import ApiError, ServiceUnavailable, UnixApiClient

    def denied(_sock, _address):
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr(socket.socket, "connect", denied)
    with pytest.raises(ApiError) as error:
        UnixApiClient().request("GET", "/api/v1/state")
    assert not isinstance(error.value, ServiceUnavailable)


@pytest.mark.parametrize("status", [403, 409, 503])
def test_http_api_error_preserves_status_and_document(unix_http, status):
    from ryuo_screen.client import ApiError, UnixApiClient

    path, _, responses = unix_http
    document = {"error": "service_error", "message": "details", "currentRevision": 17}
    responses.append((status, document))
    with pytest.raises(ApiError, match="details") as error:
        UnixApiClient(path).request("GET", "/api/v1/state")
    assert error.value.status == status
    assert error.value.document == document


@pytest.mark.parametrize(
    ("payload", "limit", "message"),
    [(b"?", 16, "JSON"), (b"[]", 16, "object"), (b" " * 32, 16, "size")],
)
def test_invalid_or_oversized_response_cannot_trigger_hid_fallback(
    unix_http, payload, limit, message
):
    from ryuo_screen.client import ApiError, UnixApiClient

    path, _, responses = unix_http
    responses.append((200, payload))
    with pytest.raises(ApiError, match=message):
        UnixApiClient(path, max_response_bytes=limit).request("GET", "/api/v1/state")


@pytest.mark.asyncio
async def test_client_uses_real_secured_api_and_revision_workflow(tmp_path):
    import asyncio
    from functools import partial

    from ryuo_screen.api import create_app
    from ryuo_screen.auth import PasswordVerifier, SecurityPolicy
    from ryuo_screen.client import ApiError, UnixApiClient
    from ryuo_screen.daemon import run_sites
    from ryuo_screen.store import AppConfig
    from test_api_security import _context

    policy = SecurityPolicy.from_config(AppConfig(
        listen_host="0.0.0.0", lan_enabled=True,
        password_verifier=PasswordVerifier.hash("test-password"),
    ))
    context, _device = _context(tmp_path, policy)
    with tempfile.TemporaryDirectory(prefix="ryu-") as directory:
        path = Path(directory) / "control.sock"
        sites = await run_sites(create_app(context), tcp=None, uds=path)
        client = UnixApiClient(path)
        run = asyncio.get_running_loop().run_in_executor
        patch = partial(client.request, "PATCH", "/api/v1/brightness",
                        {"brightness": 31, "revision": 1})
        try:
            result = await run(None, patch)
            assert result["revision"] == 2
            assert context.state_store.load().brightness == 31
            with pytest.raises(ApiError) as error:
                await run(None, patch)
            assert error.value.status == 409
            assert error.value.document["currentRevision"] == 2
        finally:
            await sites.stop()
