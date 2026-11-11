# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import time

import pytest
from aiohttp import CookieJar, web
from aiohttp.test_utils import TestClient, TestServer

from ryuo_screen.api import AppContext, create_app
from ryuo_screen.auth import (
    PasswordVerifier,
    SECURITY_KEY,
    SecurityPolicy,
    SessionStore,
)
from ryuo_screen.daemon import run_sites
from ryuo_screen.device import DeviceStatus, LatestTelemetry
from ryuo_screen.models import CommandResult, TelemetrySnapshot
from ryuo_screen.store import AppConfig, ProfileStore, ScreenState, StateStore


class Ticket:
    def snapshot(self):
        return CommandResult(saved=True, queued=True, applied=False, acked=False)


class Device:
    def __init__(self):
        self.commands = []

    def status(self):
        return DeviceStatus(phase="healthy", connected=True)

    def latest_telemetry(self):
        return LatestTelemetry(TelemetrySnapshot({}, 1.0), (), None)

    def submit(self, command):
        self.commands.append(command)
        return Ticket()


def _context(tmp_path, policy):
    state = StateStore(tmp_path / "state.json")
    state.save(ScreenState(revision=1))
    device = Device()
    context = AppContext(
        state, ProfileStore(tmp_path / "profiles"), device, object(), security=policy
    )
    return context, device


async def _client(tmp_path, policy):
    context, device = _context(tmp_path, policy)
    client = TestClient(
        TestServer(create_app(context)), cookie_jar=CookieJar(unsafe=True)
    )
    await client.start_server()
    return client, context, device


async def _raw_patch(client, headers):
    body = b'{"brightness":77}'
    reader, writer = await asyncio.open_connection(
        client.server.host, client.server.port
    )
    request = [b"PATCH /api/v1/brightness HTTP/1.1"]
    request.extend(
        "{}: {}".format(name, value).encode("ascii") for name, value in headers
    )
    request.extend(
        (
            b"If-Match: 1",
            b"Content-Type: application/json",
            "Content-Length: {}".format(len(body)).encode("ascii"),
            b"Connection: close",
            b"",
            body,
        )
    )
    writer.write(b"\r\n".join(request))
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    head, payload = response.split(b"\r\n\r\n", 1)
    status = int(head.split(b"\r\n", 1)[0].split()[1])
    text = payload.decode("utf-8")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        document = {"message": text}
    return status, document


def _local_policy():
    return SecurityPolicy.from_config(AppConfig())


def _lan_policy(clock=None, trusted_proxy="127.0.0.0/8"):
    verifier = PasswordVerifier.hash("secret-password")
    config = AppConfig(
        listen_host="0.0.0.0",
        listen_port=8746,
        lan_enabled=True,
        password_verifier=verifier,
        trusted_proxy=trusted_proxy,
    )
    session_options = {"max_sessions": 4, "lifetime": 10.0}
    if clock is not None:
        session_options["clock"] = clock
    sessions = SessionStore(**session_options)
    return SecurityPolicy.from_config(config, sessions=sessions)


def _proxy_only_policy(trusted_proxy="127.0.0.0/8"):
    return SecurityPolicy.from_config(
        AppConfig(
            listen_host="0.0.0.0",
            listen_port=8746,
            lan_enabled=True,
            trusted_proxy=trusted_proxy,
        )
    )


@pytest.mark.asyncio
async def test_loopback_host_origin_and_content_type_are_checked_before_mutation(tmp_path):
    client, context, device = await _client(tmp_path, _local_policy())
    try:
        local_get = await client.get("/api/v1/state", headers={"Host": "localhost"})
        good = await client.patch(
            "/api/v1/brightness",
            headers={"Host": "localhost", "If-Match": "1"},
            json={"brightness": 50},
        )
        revision = context.state.revision
        wrong_host = await client.patch(
            "/api/v1/brightness",
            headers={"Host": "evil.example", "If-Match": str(revision)},
            json={"brightness": 51},
        )
        foreign_origin = await client.patch(
            "/api/v1/brightness",
            headers={
                "Host": "localhost",
                "Origin": "http://evil.example",
                "If-Match": str(revision),
            },
            json={"brightness": 52},
        )
        text_plain = await client.patch(
            "/api/v1/brightness",
            headers={
                "Host": "localhost",
                "Content-Type": "text/plain",
                "If-Match": str(revision),
            },
            data='{"brightness":53}',
        )
    finally:
        await client.close()

    assert local_get.status == 200
    assert good.status == 200
    assert wrong_host.status == 403
    assert foreign_origin.status == 403
    assert text_plain.status == 415
    assert context.state.revision == revision
    assert len(device.commands) == 1


@pytest.mark.asyncio
async def test_host_ports_and_route_specific_content_types_fail_before_handlers(tmp_path):
    client, context, device = await _client(tmp_path, _local_policy())
    try:
        invalid_port = await client.get(
            "/api/v1/state", headers={"Host": "localhost:70000"}
        )
        wrong_json_type = await client.patch(
            "/api/v1/brightness",
            headers={"Host": "localhost", "If-Match": "1"},
            data=b'{"brightness":50}',
        )
        wrong_upload_type = await client.post(
            "/api/v1/media/upload",
            headers={"Host": "localhost", "Content-Type": "application/json"},
            data=b'{}',
        )
    finally:
        await client.close()

    assert invalid_port.status == 403
    assert wrong_json_type.status == 415
    assert wrong_upload_type.status == 415
    assert context.state.revision == 1
    assert device.commands == []


@pytest.mark.asyncio
async def test_lan_login_session_csrf_expiry_and_cookie_attributes(tmp_path):
    now = [100.0]
    policy = _lan_policy(clock=lambda: now[0])
    client, context, device = await _client(tmp_path, policy)
    common = {
        "Host": "192.168.1.50",
        "Origin": "http://192.168.1.50",
        "X-Forwarded-For": "192.168.1.70",
    }
    try:
        anonymous = await client.get("/api/v1/state", headers=common)
        wrong = await client.post(
            "/api/v1/auth/login", headers=common, json={"password": "wrong"}
        )
        login = await client.post(
            "/api/v1/auth/login", headers=common, json={"password": "secret-password"}
        )
        login_body = await login.json()
        cookie_header = login.headers.getall("Set-Cookie", [])
        without_csrf = await client.patch(
            "/api/v1/brightness",
            headers={**common, "If-Match": "1"},
            json={"brightness": 60},
        )
        valid = await client.patch(
            "/api/v1/brightness",
            headers={
                **common,
                "If-Match": "1",
                "X-CSRF-Token": login_body["csrfToken"],
            },
            json={"brightness": 61},
        )
        now[0] += 11.0
        expired = await client.get("/api/v1/state", headers=common)
    finally:
        await client.close()

    assert anonymous.status == 401 and wrong.status == 401
    assert login.status == 200
    assert login_body["authenticated"] is True
    assert login_body["csrfToken"]
    assert any("HttpOnly" in item and "SameSite=Strict" in item for item in cookie_header)
    assert all("Secure" not in item for item in cookie_header)
    assert without_csrf.status == 403
    assert valid.status == 200
    assert expired.status == 401
    assert context.state.brightness == 61
    assert len(device.commands) == 1


@pytest.mark.asyncio
async def test_lan_static_shell_is_public_but_api_and_mutations_stay_protected(tmp_path):
    policy = _lan_policy()
    client, context, device = await _client(tmp_path, policy)
    web_root = tmp_path / "dist"
    (web_root / "assets").mkdir(parents=True)
    (web_root / "index.html").write_text("<html>login shell</html>", encoding="utf-8")
    (web_root / "assets" / "index-AbC123xy.js").write_text("login()", encoding="utf-8")
    context.web_root = web_root
    common = {
        "Host": "192.168.1.50",
        "Origin": "http://192.168.1.50",
        "X-Forwarded-For": "192.168.1.70",
    }
    try:
        index = await client.get("/", headers=common)
        index_text = await index.text()
        head = await client.head("/", headers=common)
        asset = await client.get("/assets/index-AbC123xy.js", headers=common)
        asset_text = await asset.text()
        other = await client.get("/not-a-static-asset", headers=common)
        state = await client.get("/api/v1/state", headers=common)
        mutation = await client.patch(
            "/api/v1/brightness",
            headers={**common, "If-Match": "1"},
            json={"brightness": 50},
        )
    finally:
        await client.close()

    assert index.status == 200 and index_text == "<html>login shell</html>"
    assert head.status == 200
    assert asset.status == 200 and asset_text == "login()"
    assert other.status == 401
    assert state.status == 401
    assert mutation.status == 401
    assert context.state.revision == 1
    assert device.commands == []


@pytest.mark.asyncio
async def test_auth_status_reports_truthful_remaining_session_lifetime(tmp_path):
    now = [100.0]
    policy = _lan_policy(clock=lambda: now[0])
    client, _, _ = await _client(tmp_path, policy)
    common = {
        "Host": "192.168.1.50",
        "Origin": "http://192.168.1.50",
        "X-Forwarded-For": "192.168.1.70",
    }
    try:
        login = await client.post(
            "/api/v1/auth/login", headers=common, json={"password": "secret-password"}
        )
        login_body = await login.json()
        initial = await (await client.get("/api/v1/auth/status", headers=common)).json()
        now[0] += 3.25
        later = await (await client.get("/api/v1/auth/status", headers=common)).json()
    finally:
        await client.close()

    assert login_body["expiresIn"] == pytest.approx(10.0)
    assert initial["expiresIn"] == pytest.approx(10.0)
    assert later["expiresIn"] == pytest.approx(6.75)


@pytest.mark.asyncio
async def test_login_rotates_existing_session_and_logout_invalidates_it(tmp_path):
    policy = _lan_policy()
    client, _, _ = await _client(tmp_path, policy)
    common = {
        "Host": "192.168.1.50",
        "Origin": "http://192.168.1.50",
        "X-Forwarded-For": "192.168.1.70",
    }
    try:
        first = await client.post(
            "/api/v1/auth/login", headers=common, json={"password": "secret-password"}
        )
        first_body = await first.json()
        first_cookie = first.cookies[policy.cookie_name].value
        second = await client.post(
            "/api/v1/auth/login", headers=common, json={"password": "secret-password"}
        )
        second_body = await second.json()
        second_cookie = second.cookies[policy.cookie_name].value
        logout = await client.post(
            "/api/v1/auth/logout",
            headers={**common, "X-CSRF-Token": second_body["csrfToken"]},
            json={},
        )
        after = await client.get("/api/v1/state", headers=common)
    finally:
        await client.close()

    assert first_cookie != second_cookie
    assert policy.sessions.get(first_cookie) is None
    assert first_body["csrfToken"] != second_body["csrfToken"]
    assert logout.status == 200
    assert policy.sessions.get(second_cookie) is None
    assert after.status == 401


@pytest.mark.asyncio
async def test_forwarded_headers_are_used_only_from_configured_proxy(tmp_path):
    trusted = _lan_policy(trusted_proxy="127.0.0.0/8")
    client, _, _ = await _client(tmp_path / "trusted", trusted)
    headers = {
        "Host": "internal.invalid",
        "Origin": "https://screen.example",
        "X-Forwarded-For": "192.168.1.70",
        "X-Forwarded-Host": "screen.example",
        "X-Forwarded-Proto": "https",
    }
    try:
        response = await client.post(
            "/api/v1/auth/login", headers=headers, json={"password": "secret-password"}
        )
        cookies = response.headers.getall("Set-Cookie", [])
    finally:
        await client.close()

    untrusted = _lan_policy(trusted_proxy="10.0.0.0/8")
    other, _, _ = await _client(tmp_path / "untrusted", untrusted)
    try:
        rejected = await other.post(
            "/api/v1/auth/login", headers=headers, json={"password": "secret-password"}
        )
    finally:
        await other.close()

    assert response.status == 200
    assert any("Secure" in item for item in cookies)
    assert rejected.status == 403


@pytest.mark.asyncio
async def test_forwarded_chain_cannot_spoof_loopback_and_incomplete_forms_fail_closed(tmp_path):
    policy = _lan_policy(trusted_proxy="127.0.0.0/8")
    client, _, _ = await _client(tmp_path, policy)
    base = {
        "Host": "internal.invalid",
        "X-Forwarded-Host": "screen.example",
        "X-Forwarded-Proto": "https",
    }
    try:
        spoofed_chain = await client.get(
            "/api/v1/state",
            headers={**base, "X-Forwarded-For": "127.0.0.1, 192.168.1.70"},
        )
        missing_client = await client.get("/api/v1/state", headers=base)
        standard_forwarded = await client.get(
            "/api/v1/state",
            headers={
                "Host": "internal.invalid",
                "Forwarded": "for=127.0.0.1;host=screen.example;proto=https",
            },
        )
    finally:
        await client.close()

    assert spoofed_chain.status == 401
    assert missing_client.status == 403
    assert standard_forwarded.status == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("trusted_proxy", ["127.0.0.0/8", "10.0.0.0/8"])
async def test_duplicate_security_headers_fail_closed_before_mutation(
    tmp_path, trusted_proxy
):
    policy = _lan_policy(trusted_proxy=trusted_proxy)
    client, context, device = await _client(tmp_path, policy)
    cases = {
        "Host": [
            ("Host", "192.168.1.50"),
            ("Host", "192.168.1.50"),
            ("Origin", "http://192.168.1.50"),
        ],
        "Origin": [
            ("Host", "192.168.1.50"),
            ("Origin", "http://192.168.1.50"),
            ("Origin", "http://192.168.1.50"),
        ],
        "Forwarded": [
            ("Host", "192.168.1.50"),
            ("Origin", "http://192.168.1.50"),
            ("Forwarded", "for=192.168.1.70"),
            ("Forwarded", "for=127.0.0.1"),
        ],
        "X-Forwarded-For": [
            ("Host", "192.168.1.50"),
            ("Origin", "http://192.168.1.50"),
            ("X-Forwarded-For", "127.0.0.1"),
            ("X-Forwarded-For", "192.168.1.70"),
        ],
        "X-Forwarded-Host": [
            ("Host", "internal.invalid"),
            ("Origin", "https://screen.example"),
            ("X-Forwarded-For", "192.168.1.70"),
            ("X-Forwarded-Host", "screen.example"),
            ("X-Forwarded-Host", "localhost"),
            ("X-Forwarded-Proto", "https"),
        ],
        "X-Forwarded-Proto": [
            ("Host", "internal.invalid"),
            ("Origin", "https://screen.example"),
            ("X-Forwarded-For", "192.168.1.70"),
            ("X-Forwarded-Host", "screen.example"),
            ("X-Forwarded-Proto", "https"),
            ("X-Forwarded-Proto", "http"),
        ],
    }
    try:
        for name, raw_headers in cases.items():
            status, body = await _raw_patch(client, raw_headers)
            assert status == (400 if name == "Host" else 403), name
            assert "duplicate" in body["message"].lower(), name
    finally:
        await client.close()

    assert context.state.revision == 1
    assert context.state.brightness != 77
    assert device.commands == []


@pytest.mark.asyncio
async def test_trusted_proxy_can_be_the_explicit_lan_security_boundary(tmp_path):
    policy = _proxy_only_policy()
    policy.validate_bind("0.0.0.0")
    client, _, _ = await _client(tmp_path, policy)
    headers = {
        "Host": "internal.invalid",
        "X-Forwarded-For": "192.168.1.70",
        "X-Forwarded-Host": "screen.example",
        "X-Forwarded-Proto": "https",
    }
    try:
        response = await client.get("/api/v1/state", headers=headers)
        status = await client.get("/api/v1/auth/status", headers=headers)
        status_body = await status.json()
    finally:
        await client.close()

    assert response.status == 200
    assert status_body == {
        "required": False,
        "authenticated": True,
        "csrfToken": None,
    }


@pytest.mark.asyncio
async def test_slow_scrypt_login_does_not_block_event_loop(tmp_path, monkeypatch):
    policy = _lan_policy()
    client, _, _ = await _client(tmp_path, policy)

    def slow_verify(_password, _encoded):
        time.sleep(0.15)
        return False

    monkeypatch.setattr(PasswordVerifier, "verify", slow_verify)
    headers = {
        "Host": "192.168.1.50",
        "Origin": "http://192.168.1.50",
        "X-Forwarded-For": "192.168.1.70",
    }
    try:
        started = asyncio.get_running_loop().time()
        request = asyncio.create_task(
            client.post(
                "/api/v1/auth/login", headers=headers, json={"password": "wrong"}
            )
        )
        await asyncio.sleep(0.02)
        elapsed = asyncio.get_running_loop().time() - started
        response = await request
    finally:
        await client.close()

    assert elapsed < 0.08
    assert response.status == 401


@pytest.mark.asyncio
async def test_loopback_request_needs_no_login_even_when_lan_is_enabled(tmp_path):
    client, _, _ = await _client(tmp_path, _lan_policy())
    try:
        state = await client.get("/api/v1/state", headers={"Host": "localhost"})
        status = await client.get(
            "/api/v1/auth/status", headers={"Host": "localhost"}
        )
        body = await status.json()
    finally:
        await client.close()

    assert state.status == 200
    assert body == {"required": False, "authenticated": True, "csrfToken": None}


@pytest.mark.asyncio
async def test_non_loopback_startup_fails_before_runner_without_lan_password(
    monkeypatch,
):
    app = web.Application()
    called = []

    class ForbiddenRunner:
        def __init__(self, _app):
            called.append(True)
            raise AssertionError("runner must not be opened")

    monkeypatch.setattr(web, "AppRunner", ForbiddenRunner)
    insecure = SecurityPolicy.from_config(
        AppConfig(listen_host="0.0.0.0", lan_enabled=False)
    )
    with pytest.raises(ValueError, match="LAN"):
        await run_sites(
            app, tcp=("0.0.0.0", 0), uds=None, security=insecure
        )
    assert called == []


def test_non_loopback_policy_requires_password_and_valid_proxy_cidrs():
    verifier = PasswordVerifier.hash("secret-password")
    with pytest.raises(ValueError, match="password"):
        SecurityPolicy.from_config(
            AppConfig(listen_host="0.0.0.0", lan_enabled=True)
        )

    proxy_only = _proxy_only_policy("127.0.0.1/32")
    assert proxy_only.verifier is None
    assert "verifier" not in repr(proxy_only).lower()
    with pytest.raises(ValueError, match="proxy"):
        SecurityPolicy.from_config(
            AppConfig(
                listen_host="0.0.0.0",
                lan_enabled=True,
                password_verifier=verifier,
                trusted_proxy="not-a-cidr",
            )
        )


@pytest.mark.asyncio
async def test_non_loopback_startup_cannot_use_policy_different_from_middleware():
    app = web.Application()
    app_policy = _local_policy()
    app[SECURITY_KEY] = app_policy
    with pytest.raises(ValueError, match="application security policy"):
        await run_sites(
            app,
            tcp=("0.0.0.0", 0),
            uds=None,
            security=_lan_policy(),
        )
