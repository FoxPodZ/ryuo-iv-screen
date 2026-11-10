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
        assert [item["slug"] for item in listing["profiles"]] == ["gaming"]

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
