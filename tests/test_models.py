# SPDX-License-Identifier: GPL-3.0-or-later
"""Contracts for service models, independent of hardware."""

import json
from dataclasses import asdict
from typing import Sequence, get_type_hints

import pytest

from ryuo_screen.models import (
    Command,
    CommandResult,
    Measurement,
    SensorDescriptor,
    SensorRef,
    TelemetrySnapshot,
)
from ryuo_screen.telemetry.base import TelemetryProvider


def test_sensor_ref_json_roundtrip_has_no_hwmon_index():
    ref = SensorRef(provider="hwmon", device="0000:03:00.0", channel="temp1")
    decoded = json.loads(json.dumps(ref.to_dict()))

    assert decoded == {
        "provider": "hwmon",
        "device": "0000:03:00.0",
        "channel": "temp1",
    }
    assert asdict(ref) == decoded
    restored = SensorRef.from_dict(decoded)
    assert restored == ref
    assert restored.stable_id == ref.stable_id
    assert "hwmon0" not in ref.stable_id
    assert "card0" not in ref.stable_id


def test_sensor_ref_stable_id_distinguishes_field_boundaries():
    first = SensorRef("hwmon", "pci/device", "temp1")
    second = SensorRef("hwmon", "pci", "device/temp1")

    assert first.stable_id != second.stable_id


@pytest.mark.parametrize("field", ["provider", "device", "channel"])
def test_sensor_ref_rejects_nul(field):
    data = {"provider": "hwmon", "device": "amdgpu", "channel": "temp1"}
    data[field] += "\x00"

    with pytest.raises(ValueError):
        SensorRef.from_dict(data)


@pytest.mark.parametrize("field", ["provider", "device", "channel"])
@pytest.mark.parametrize("from_json", [False, True])
def test_sensor_ref_rejects_non_string_components(field, from_json):
    data = {"provider": "hwmon", "device": "amdgpu", "channel": "temp1"}
    data[field] = []

    with pytest.raises(TypeError):
        if from_json:
            SensorRef.from_dict(json.loads(json.dumps(data)))
        else:
            SensorRef(**data)


def test_sensor_descriptor_fields():
    ref = SensorRef("hwmon", "0000:03:00.0", "temp1")
    descriptor = SensorDescriptor(ref, "gpu.temperature", "GPU edge", "°C")

    assert asdict(descriptor) == {
        "ref": {"provider": "hwmon", "device": "0000:03:00.0", "channel": "temp1"},
        "measurement_id": "gpu.temperature",
        "label": "GPU edge",
        "unit": "°C",
        "available": True,
        "source": None,
        "metadata": {},
        "error": None,
    }


@pytest.mark.parametrize("error", ["sensor disappeared", None])
def test_measurement_unavailable_keeps_error(error):
    ref = SensorRef("hwmon", "0000:03:00.0", "temp1")
    measurement = Measurement(
        ref, "gpu.temperature", None, "°C", 123.5, available=False, error=error
    )
    decoded = json.loads(json.dumps(asdict(measurement)))

    assert decoded == {
        "ref": {"provider": "hwmon", "device": "0000:03:00.0", "channel": "temp1"},
        "measurement_id": "gpu.temperature",
        "value": None,
        "unit": "°C",
        "sampled_at": 123.5,
        "available": False,
        "error": error,
    }
    decoded["ref"] = SensorRef.from_dict(decoded["ref"])
    assert Measurement(**decoded) == measurement


def test_telemetry_snapshot_uses_measurement_ids_as_keys():
    ref = SensorRef("hwmon", "0000:03:00.0", "temp1")
    measurement = Measurement(ref, "gpu.temperature", 46.5, "°C", 123.5)
    snapshot = TelemetrySnapshot({"gpu.temperature": measurement}, 123.5)

    assert asdict(snapshot) == {
        "measurements": {"gpu.temperature": asdict(measurement)},
        "sampled_at": 123.5,
        "errors": {},
    }


def test_command_fields():
    command = Command(method="POST", resource="all", payload={"gpu": {"load": 30}})

    assert asdict(command) == {
        "method": "POST",
        "resource": "all",
        "payload": {"gpu": {"load": 30}},
        "priority": 100,
        "coalesce_key": None,
    }


def test_command_result_distinguishes_saved_queued_applied_acked():
    defaults = {
        "saved": False,
        "queued": False,
        "applied": False,
        "acked": False,
        "error": None,
    }
    assert asdict(CommandResult()) == defaults

    results = []
    for flag in ("saved", "queued", "applied", "acked"):
        result = CommandResult(**{flag: True})
        decoded = json.loads(json.dumps(asdict(result)))

        assert decoded == dict(defaults, **{flag: True})
        assert CommandResult(**decoded) == result
        results.append(result)

    assert len(set(results)) == 4


def test_telemetry_provider_contract():
    assert get_type_hints(TelemetryProvider)["provider_id"] is str
    assert get_type_hints(TelemetryProvider.probe) == {
        "return": Sequence[SensorDescriptor],
    }
    assert get_type_hints(TelemetryProvider.sample) == {
        "return": TelemetrySnapshot,
    }
