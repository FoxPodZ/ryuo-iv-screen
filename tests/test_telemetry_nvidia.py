# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess

import pytest

import ryuo_send
from ryuo_screen.telemetry.nvidia import NvidiaProvider


def _fake_smi(rows):
    def run(cmd, **kwargs):
        assert cmd[0] == "test-nvidia-smi"
        assert cmd[2] == "--format=csv,noheader,nounits"
        query = cmd[1].split("=", 1)[1].split(",")
        stdout = "\n".join(", ".join(row[field] for field in query) for row in rows)
        return subprocess.CompletedProcess(cmd, 0, stdout, "")
    return run


_FIRST = {
    "index": "4", "uuid": "GPU-uuid-first", "name": "NVIDIA RTX First",
    "temperature.gpu": "63", "utilization.gpu": "42", "power.draw": "84.70",
    "clocks.current.graphics": "1910", "fan.speed": "36", "memory.used": "700",
    "memory.total": "8192",
}
_SECOND = {
    **_FIRST, "index": "0", "uuid": "GPU-uuid-second", "name": "NVIDIA RTX Second",
    "temperature.gpu": "49", "fan.speed": "[N/A]",
}


def test_nvidia_full_stats_include_correct_fan_and_vram_units():
    provider = NvidiaProvider(executable="test-nvidia-smi", runner=_fake_smi([_FIRST]))
    sample = provider.sample().measurements
    assert {key: (m.value, m.unit) for key, m in sample.items()} == {
        "gpu.temperature": (63, "°C"), "gpu.load": (42, "%"),
        "gpu.power": (84.7, "W"), "gpu.clock.core": (1910, "MHz"),
        "gpu.fan": (36, "%"), "gpu.vram.used": (734003200, "B"),
        "gpu.vram.total": (8589934592, "B"),
    }
    assert {m.ref.device for m in sample.values()} == {"GPU-uuid-first"}


@pytest.mark.parametrize("selector", [0, "0", "GPU-uuid-second"])
def test_nvidia_selects_exact_uuid_or_index_and_na_only_affects_one_field(selector):
    provider = NvidiaProvider(selector, executable="test-nvidia-smi",
                              runner=_fake_smi([_FIRST, _SECOND]))
    snapshot = provider.sample()

    assert snapshot.measurements["gpu.temperature"].value == 49
    assert snapshot.measurements["gpu.power"].value == 84.7
    fan = snapshot.measurements["gpu.fan"]
    assert not fan.available and fan.error and fan.value is None
    descriptors = provider.probe()
    assert {d.ref.device for d in descriptors} == {"GPU-uuid-first", "GPU-uuid-second"}
    assert {d.ref.device for d in descriptors if d.metadata["selected"]} == {"GPU-uuid-second"}


def test_missing_nvidia_selector_does_not_switch_cards():
    provider = NvidiaProvider("GPU-uuid-missing", executable="test-nvidia-smi",
                              runner=_fake_smi([_FIRST]))
    snapshot = provider.sample()
    assert not snapshot.measurements
    assert "GPU-uuid-missing" in snapshot.errors["nvidia"]


def test_nvidia_timeout_is_an_unavailable_provider():
    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
    provider = NvidiaProvider(executable="test-nvidia-smi", runner=timeout)
    snapshot = provider.sample()
    assert not snapshot.measurements
    assert "timed out" in snapshot.errors["nvidia"]


def test_legacy_nvidia_wrapper_preserves_shape_and_samples_each_tick(monkeypatch):
    from ryuo_screen.telemetry import nvidia

    rows = [_FIRST.copy()]
    monkeypatch.setattr(ryuo_send, "_NVIDIA_PROVIDER", NvidiaProvider(include_vram=False))
    monkeypatch.setattr(nvidia.shutil, "which", lambda name: "test-nvidia-smi")
    monkeypatch.setattr(nvidia.subprocess, "run", _fake_smi(rows))
    assert ryuo_send._nvidia() == {"name": "NVIDIA RTX First", "stats": {
        "hasDedicated": True, "load": 42, "temperature": 63, "fan": 36,
        "speed": 1910, "power": 84, "voltage": 0,
    }}

    rows[0].update({"temperature.gpu": "59", "fan.speed": "[N/A]"})
    assert ryuo_send._nvidia()["stats"]["temperature"] == 59
    assert ryuo_send._nvidia()["stats"]["fan"] == 0


def test_runtime_gpu_selection_uses_uuid_and_rejects_unstable_index():
    from ryuo_screen.models import SensorRef
    from ryuo_screen.telemetry.collector import TelemetryCollector

    provider = NvidiaProvider(4, executable="test-nvidia-smi", runner=_fake_smi([_FIRST, _SECOND]))
    collector = TelemetryCollector([provider])
    collector.set_selectors({"gpu": SensorRef("nvidia", "GPU-uuid-second", "gpu.temperature")})
    assert collector.sample().measurements["gpu.temperature"].value == 49
    collector.set_selectors({"gpu": SensorRef("nvidia", "0", "gpu.temperature")})
    sample = collector.sample()
    assert not sample.measurements and sample.errors
    collector.set_selectors({})
    assert collector.sample().measurements["gpu.temperature"].value == 63
