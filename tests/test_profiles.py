# SPDX-License-Identifier: GPL-3.0-or-later
"""Named profile CRUD, validation and import/export tests."""

import json
from dataclasses import replace

import pytest

from ryuo_screen.models import SensorRef
from ryuo_screen.store import (
    Profile,
    ProfileConflict,
    ProfileNotFound,
    ProfileStore,
    SlotAssignment,
    default_miku_profiles,
)


def profile(slug="gaming", name="Gaming"):
    slots = tuple(
        SlotAssignment(
            enabled=index < 3,
            measurement_id=measurement,
            widget=widget,
            label=("CPU" if index == 0 else None),
        )
        for index, (measurement, widget) in enumerate(
            (
                ("cpu.temperature", "CPU Temperature"),
                ("gpu.temperature", "GPU Temperature"),
                ("gpu.load", "GPU Usage"),
                ("", ""),
                ("", ""),
                ("", ""),
            )
        )
    )
    return Profile(
        slug=slug,
        name=name,
        media=(("custom-loop.mp4",),),
        playback_modes=("Cycle",),
        slots=slots,
        brightness=88,
        refresh_interval=1.5,
        title_colors=("#E5252B",),
        content_colors=("#FFFFFF",),
        opacity=90,
        rgb_mode="thermal",
        rgb_target="value",
        thermal_source="cpu.temperature",
        sensor_selectors={
            "gpu": SensorRef("amd", "0000:03:00.0", "edge")
        },
    )


def test_profile_crud_rename_duplicate_and_restart(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    created = store.create(profile())

    assert created == profile()
    assert store.get("gaming") == profile()
    assert [item for item in store.list() if not item.factory] == [profile()]

    renamed = store.update("gaming", profile("games", "Games"))
    assert renamed.slug == "games"
    with pytest.raises(ProfileNotFound):
        store.get("gaming")

    copied = store.duplicate("games", "Games Copy", "games-copy")
    assert copied.slug == "games-copy"
    assert copied.name == "Games Copy"
    assert copied.media == renamed.media
    assert copied.factory is False

    assert [item.slug for item in ProfileStore(store.directory).list() if not item.factory] == [
        "games",
        "games-copy",
    ]
    store.delete("games-copy")
    with pytest.raises(ProfileNotFound):
        store.get("games-copy")


def test_profile_slug_conflicts_are_never_overwritten(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    store.create(profile())

    with pytest.raises(ProfileConflict):
        store.create(profile(name="Different"))
    with pytest.raises(ProfileConflict):
        store.duplicate("gaming", "Copy", "gaming")

    assert store.get("gaming").name == "Gaming"


@pytest.mark.parametrize(
    "change, error",
    [
        ({"slots": profile().slots[:5]}, "six"),
        ({"brightness": 103}, "brightness"),
        ({"playback_modes": ("Loop",)}, "playback"),
        ({"screen_mode": "Unsupported"}, "screen"),
        ({"opacity": 101}, "opacity"),
        ({"refresh_interval": 0}, "refresh"),
    ],
)
def test_profile_validation(change, error):
    values = profile().to_dict()
    values.update(change)

    with pytest.raises((TypeError, ValueError), match=error):
        Profile.from_dict(values)


def test_profile_import_rejects_unknown_or_future_schema(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    valid = profile().to_dict()

    with pytest.raises(ValueError, match="schema"):
        store.import_profile(dict(valid, schema_version=99))
    with pytest.raises(ValueError, match="unknown"):
        store.import_profile(dict(valid, password_verifier="secret"))

    assert all(item.factory for item in store.list())
    assert not store.directory.exists()


def test_profile_export_round_trip_has_no_runtime_secrets(tmp_path):
    store = ProfileStore(tmp_path / "profiles", runtime_secrets={"session": "secret"})
    store.create(profile())

    exported = store.export_profile("gaming")
    document = json.loads(exported)

    assert "secret" not in exported
    assert "runtime" not in document
    assert "password" not in document
    imported = ProfileStore(tmp_path / "other").import_profile(exported)
    assert imported == profile()


def test_factory_profile_cannot_be_deleted(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    factory = default_miku_profiles()[0]

    with pytest.raises(PermissionError, match="factory"):
        store.delete(factory.slug)


def test_factory_profile_cannot_be_demoted_then_deleted(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    factory = default_miku_profiles()[0]

    with pytest.raises(PermissionError, match="factory"):
        store.update(factory.slug, replace(factory, factory=False))
    with pytest.raises(PermissionError, match="factory"):
        store.delete(factory.slug)

    assert store.get(factory.slug) == factory


def test_factory_profile_media_and_identity_cannot_be_mutated(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    factory = default_miku_profiles()[0]
    changed = replace(
        factory,
        slug="changed-factory",
        name="Changed Factory",
        media=(("renamed.mp4",),),
    )

    with pytest.raises(PermissionError, match="factory"):
        store.update(factory.slug, changed)

    assert store.get(factory.slug) == factory
    with pytest.raises(ProfileNotFound):
        store.get(changed.slug)


def test_default_miku_profiles_pin_exact_factory_media_order():
    profiles = default_miku_profiles()
    filenames = [f"Ryuo_IV_MIKU_WW_{index:02d}.mp4" for index in range(1, 5)]

    assert len(profiles) == 5
    assert [item.name for item in profiles[:4]] == [
        "Miku Single 01",
        "Miku Single 02",
        "Miku Single 03",
        "Miku Single 04",
    ]
    assert [item.media for item in profiles[:4]] == [((name,),) for name in filenames]
    assert all(item.playback_modes == ("Single",) for item in profiles[:4])
    assert profiles[4].name == "Miku Cycle"
    assert profiles[4].media == (tuple(filenames),)
    assert profiles[4].playback_modes == ("Cycle",)
    assert all(item.factory for item in profiles)


def test_profile_files_use_group_readable_state_mode(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    store.create(profile())

    assert (store.directory / "gaming.json").stat().st_mode & 0o777 == 0o640


def test_profile_listing_migrates_old_empty_playlist_and_skips_invalid_json_root(tmp_path):
    store = ProfileStore(tmp_path)
    (tmp_path / "invalid.json").write_text("[]")
    (tmp_path / "old.json").write_text(json.dumps({
        "slug": "old", "name": "Old", "brightness": 19, "media": [[]], "playback_modes": ["Random"]
    }))
    custom = [p for p in store.list() if not p.factory]
    assert [(p.slug, p.brightness, p.playback_modes) for p in custom] == [("old", 19, ("Single",))]
