# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ryuo_screen.api import AppContext, create_app
from ryuo_screen.device import LatestTelemetry
from ryuo_screen.models import CommandResult, TelemetrySnapshot
from ryuo_screen.store import ProfileStore, ScreenState, StateStore


class FakeTicket:
    def snapshot(self):
        return CommandResult(saved=True, queued=True)


class FakeDevice:
    def __init__(self):
        self.commands = []

    def submit(self, command):
        self.commands.append(command)
        return FakeTicket()

    def status(self):
        return type("Status", (), {"phase": "disconnected", "connected": False})()

    def latest_telemetry(self):
        return LatestTelemetry()


class FakeTelemetry:
    def sample(self):
        return TelemetrySnapshot({}, 1.0)

    def catalog(self):
        return ()


async def _client(tmp_path):
    state_store = StateStore(tmp_path / "state.json")
    state_store.save(ScreenState(revision=2))
    context = AppContext(
        state_store,
        ProfileStore(tmp_path / "profiles"),
        FakeDevice(),
        FakeTelemetry(),
    )
    client = TestClient(TestServer(create_app(context)))
    await client.start_server()
    return client, context


def _profile(slug="gaming", name="Gaming"):
    return {
        "slug": slug,
        "name": name,
        "media": [["loop.mp4"]],
        "playback_modes": ["Cycle"],
        "brightness": 50,
    }


@pytest.mark.asyncio
async def test_profile_crud_import_export_and_apply(tmp_path):
    client, context = await _client(tmp_path)
    try:
        created = await client.post("/api/v1/profiles", json=_profile())
        assert created.status == 201
        assert (await created.json())["profile"]["factory"] is False

        listing = await (await client.get("/api/v1/profiles")).json()
        assert [item["slug"] for item in listing["profiles"] if not item["factory"]] == ["gaming"]

        updated = await client.patch(
            "/api/v1/profiles/gaming", json={"slug": "night", "name": "Night", "brightness": 15}
        )
        assert updated.status == 200
        assert (await updated.json())["profile"]["slug"] == "night"

        duplicated = await client.post(
            "/api/v1/profiles/night/duplicate",
            json={"slug": "night-copy", "name": "Night Copy"},
        )
        assert duplicated.status == 201
        assert (await duplicated.json())["profile"]["brightness"] == 15

        exported = await client.get("/api/v1/profiles/night/export")
        assert exported.status == 200
        export_document = json.loads(await exported.text())
        assert export_document["brightness"] == 15
        assert "password" not in str(export_document).lower()

        imported_document = _profile("imported", "Imported")
        imported_document["factory"] = True
        imported = await client.post("/api/v1/profiles/import", json=imported_document)
        assert imported.status == 201
        assert (await imported.json())["profile"]["factory"] is False

        applied = await client.post(
            "/api/v1/profiles/night/apply",
            headers={"If-Match": "2"},
            json={},
        )
        applied_body = await applied.json()
        assert applied.status == 200
        assert applied_body["revision"] == 3
        assert applied_body["saved"] is True
        saved = context.state_store.load()
        assert saved.active_profile == "night"
        assert saved.brightness == 15

        deleted = await client.delete("/api/v1/profiles/imported")
        assert deleted.status == 204
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_profile_errors_are_structured_and_do_not_mutate(tmp_path):
    client, context = await _client(tmp_path)
    try:
        invalid = await client.post(
            "/api/v1/profiles", json={**_profile(), "slots": []}
        )
        missing = await client.get("/api/v1/profiles/not-here")
        stale = await client.post(
            "/api/v1/profiles/not-here/apply",
            headers={"If-Match": "1"},
            json={},
        )
        invalid_body = await invalid.json()
        missing_body = await missing.json()
        stale_body = await stale.json()
    finally:
        await client.close()
    assert invalid.status == 400
    assert invalid_body["error"] == "validation_error"
    assert missing.status == 404
    assert missing_body["error"] == "not_found"
    assert stale.status == 409
    assert stale_body["currentRevision"] == 2
    assert context.state_store.load().revision == 2


@pytest.mark.asyncio
async def test_builtin_profiles_are_virtual_and_support_api_workflows(tmp_path):
    client, context = await _client(tmp_path)
    try:
        listing = await (await client.get("/api/v1/profiles")).json()
        assert {profile["name"] for profile in listing["profiles"]} == {
            "Miku Single 01", "Miku Single 02", "Miku Single 03", "Miku Single 04", "Miku Cycle",
        }
        assert all(profile["factory"] for profile in listing["profiles"])
        path = "/api/v1/profiles/miku-cycle"
        fetched = await client.get(path)
        assert (await fetched.json())["profile"]["factory"]
        exported = await (await client.get(path + "/export")).json()
        assert exported["media"] == [[f"Ryuo_IV_MIKU_WW_{n:02d}.mp4" for n in range(1, 5)]]
        assert (await client.post(path + "/apply", json={"revision": 2})).status == 200
        assert context.state.active_profile == "miku-cycle"
        assert (await client.patch(path, json={"name": "Changed"})).status == 403
        assert (await client.delete(path)).status == 403
        assert (await client.post("/api/v1/profiles", json=_profile("miku-cycle"))).status == 409
        assert (await client.post("/api/v1/profiles/import", json=exported)).status == 409
        duplicated = await client.post(path + "/duplicate", json={"name": "Own Copy"})
        assert duplicated.status == 201
        result = (await duplicated.json())["profile"]
        assert not result["factory"] and result["media"] == exported["media"]
        assert sorted(p.name for p in context.profile_store.directory.iterdir()) == ["own-copy.json"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_connected_profile_apply_reports_both_zones_and_matches_case(tmp_path):
    from ryuo_screen.device import DeviceStatus
    client, context = await _client(tmp_path)
    async with client:
        context.device.status = lambda: DeviceStatus(connected=True, descriptor={
            "media": {"preset": ["P.PNG"], "custom": ["c.png"]}})
        p = dict(_profile(), screen_mode="Screen Splitting", playback_modes=["Single", "Single"],
                 media=[["p.png", "absent1"], ["C.PNG", "absent2"]],
                 title_colors=["#FFFFFF"] * 2, content_colors=["#FFFFFF"] * 2)
        assert (await client.post("/api/v1/profiles", json=p)).status == 201
        url = "/api/v1/profiles/gaming"
        rejected = await client.post(url + "/apply", json={"revision": 2})
        assert rejected.status == 400
        message = (await rejected.json())["message"]
        assert "1" in message and "absent1" in message and "2" in message and "absent2" in message
        assert not context.device.commands
        assert (await client.patch(url, json={"media": [["p.png"], ["C.PNG"]]})).status == 200
        assert (await client.post(url + "/apply", json={"revision": 2})).status == 200
