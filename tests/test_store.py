# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistence tests for daemon configuration and mutable screen state."""

import json
import os
from pathlib import Path

import pytest

from ryuo_screen.models import SensorRef
from ryuo_screen.store import (
    AppConfig,
    ScreenState,
    SlotAssignment,
    StateStore,
    write_secret,
)


def slots():
    return tuple(
        SlotAssignment(enabled=index < 2, measurement_id=value, widget=value)
        for index, value in enumerate(
            ("CPU Temperature", "GPU Temperature", "", "", "", "")
        )
    )


def state():
    return ScreenState(
        revision=7,
        active_profile="gaming",
        screen_mode="Screen Splitting",
        media=(("left.mp4",), ("right.png",)),
        playback_modes=("Cycle", "Single"),
        slots=slots(),
        brightness=91,
        temperature_unit="Fahrenheit",
        refresh_interval=2.5,
        title_colors=("#112233", "#445566"),
        content_colors=("#FFFFFF", "#EEEEEE"),
        opacity=84,
        rgb_mode="thermal",
        rgb_target="both",
        thermal_source="gpu.temperature",
        sensor_selectors={
            "gpu": SensorRef("amd", "0000:03:00.0", "edge"),
            "motherboard": SensorRef("hwmon", "platform/nct6799", "temp2"),
        },
    )


def test_app_config_loads_toml_and_uses_service_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
data_dir = "/srv/ryuo"
listen_host = "127.0.0.1"
listen_port = 9123
gpu_provider = "amd"
gpu_selector = "0000:03:00.0"

[motherboard_sensor]
provider = "hwmon"
device = "platform/nct6799"
channel = "temp2"
""".strip(),
        encoding="utf-8",
    )

    loaded = AppConfig.load(path)

    assert loaded.config_path == path
    assert loaded.data_dir == Path("/srv/ryuo")
    assert loaded.state_path == Path("/srv/ryuo/state.json")
    assert loaded.profiles_dir == Path("/srv/ryuo/profiles")
    assert loaded.listen_host == "127.0.0.1"
    assert loaded.listen_port == 9123
    assert loaded.gpu_provider == "amd"
    assert loaded.gpu_selector == "0000:03:00.0"
    assert loaded.motherboard_sensor == SensorRef(
        "hwmon", "platform/nct6799", "temp2"
    )


def test_app_config_missing_file_uses_documented_paths(tmp_path):
    loaded = AppConfig.load(tmp_path / "missing.toml")

    assert loaded.config_path == tmp_path / "missing.toml"
    assert loaded.data_dir == Path("/var/lib/ryuo-screen")
    assert loaded.state_path == Path("/var/lib/ryuo-screen/state.json")
    assert loaded.profiles_dir == Path("/var/lib/ryuo-screen/profiles")
    assert loaded.listen_host == "127.0.0.1"


@pytest.mark.parametrize(
    "document, field",
    [
        ('lan_enabled = "false"\n', "lan_enabled"),
        ("[security]\npassword_verifier = 123\n", "password_verifier"),
        ('[security]\ntrusted_proxy = ["127.0.0.1"]\n', "trusted_proxy"),
    ],
)
def test_app_config_rejects_wrong_security_field_types(tmp_path, document, field):
    path = tmp_path / "config.toml"
    path.write_text(document, encoding="utf-8")

    with pytest.raises(TypeError, match=field):
        AppConfig.load(path)


def test_state_restart_round_trip_and_permissions(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)

    store.save(state())
    restored = StateStore(path).load()

    assert restored == state()
    assert path.stat().st_mode & 0o777 == 0o640


def test_state_save_rejects_multibyte_config_before_replacing_desired_state(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save(ScreenState(revision=1))
    original = path.read_bytes()
    label = "🔥" * 32
    oversized = ScreenState(
        revision=2,
        slots=tuple(
            SlotAssignment(True, "fan.{}.rpm".format(index),
                           "Fan Speed " + label, label)
            for index in range(6)
        ),
    )

    with pytest.raises(ValueError, match="1024-byte report"):
        store.save(oversized)

    assert path.read_bytes() == original
    assert store.load().revision == 1


def test_state_save_fsyncs_temp_and_parent_before_atomic_replace(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    calls = []
    original_replace = os.replace
    original_fsync = os.fsync

    def fsync(fd):
        calls.append(("fsync", os.fstat(fd).st_mode))
        return original_fsync(fd)

    def replace(source, destination):
        calls.append(("replace", Path(source).name, Path(destination)))
        assert Path(source).parent == path.parent
        assert json.loads(Path(source).read_text(encoding="utf-8"))["revision"] == 7
        return original_replace(source, destination)

    monkeypatch.setattr("ryuo_screen.store.os.fsync", fsync)
    monkeypatch.setattr("ryuo_screen.store.os.replace", replace)

    StateStore(path).save(state())

    replace_index = next(i for i, call in enumerate(calls) if call[0] == "replace")
    assert any(call[0] == "fsync" for call in calls[:replace_index])
    assert any(call[0] == "fsync" for call in calls[replace_index + 1 :])


def test_state_load_migrates_unversioned_legacy_shape(tmp_path):
    path = tmp_path / "state.json"
    legacy = {
        "revision": 2,
        "profile": "quiet",
        "brightness": 40,
        "assignments": [
            {"enabled": True, "measurement_id": "cpu.temperature", "widget": "CPU Temperature"}
        ]
        + [{"enabled": False, "measurement_id": "", "widget": ""}] * 5,
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = StateStore(path).load()

    assert loaded.schema_version == 1
    assert loaded.revision == 2
    assert loaded.active_profile == "quiet"
    assert loaded.brightness == 40
    assert len(loaded.slots) == 6
    # Loading is read-only; migration is persisted on the next explicit save.
    assert "schema_version" not in json.loads(path.read_text(encoding="utf-8"))


def test_malformed_state_recovers_without_overwriting_evidence(tmp_path):
    path = tmp_path / "state.json"
    malformed = b'{"schema_version": 1, "brightness": '
    path.write_bytes(malformed)
    store = StateStore(path)

    loaded = store.load()

    assert loaded == ScreenState()
    assert store.last_error and "state" in store.last_error.lower()
    assert path.read_bytes() == malformed


def test_future_state_schema_is_not_silently_downgraded(tmp_path):
    path = tmp_path / "state.json"
    payload = {"schema_version": 99, "revision": 10}
    path.write_text(json.dumps(payload), encoding="utf-8")
    store = StateStore(path)

    loaded = store.load()

    assert loaded == ScreenState()
    assert "schema version" in store.last_error.lower()
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_secret_writer_uses_owner_only_mode(tmp_path):
    path = tmp_path / "session.secret"

    write_secret(path, "not-plaintext-password-but-still-secret")

    assert path.read_text(encoding="utf-8") == "not-plaintext-password-but-still-secret"
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("brightness", [-1, 103, True])
def test_screen_state_rejects_invalid_brightness(brightness):
    with pytest.raises((TypeError, ValueError)):
        ScreenState(brightness=brightness)


def test_screen_state_requires_exactly_six_slots():
    with pytest.raises(ValueError, match="six"):
        ScreenState(slots=slots()[:5])
