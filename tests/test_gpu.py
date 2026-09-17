#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 FoxPodZ (foxpodz.de)
"""
GPU telemetry tests for ryuo_send. No hardware needed.

    pip install pytest
    pytest tests/ -v

The Linux path is checked against fake sysfs trees, so it stays testable from
a machine that isn't Linux — which is the whole point, since the person with
the cooler and the person with an AMD card are rarely the same person.

The Windows path can only be checked where D3DKMT exists; everywhere else the
one thing worth asserting is that it declines politely instead of raising.
"""
import os
import platform
import sys
import types

try:
    import pytest
except ImportError:
    # Running this file directly as a GPU probe (see the bottom) only needs
    # ryuo_send. The tests themselves still need a real pytest; this stub just
    # keeps the decorators from blowing up at import time.
    pytest = types.SimpleNamespace(
        mark=types.SimpleNamespace(skipif=lambda *a, **k: (lambda f: f),
                                   parametrize=lambda *a, **k: (lambda f: f)),
        skip=lambda *a, **k: None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# ryuo_send imports hid at module level, which needs the library installed and
# has nothing to do with reading sensors. A stub keeps these tests dependency
# -free; nothing here touches the device.
sys.modules.setdefault("hid", types.ModuleType("hid"))
import ryuo_send as send                                  # noqa: E402

AMD, INTEL, NVIDIA = "0x1002", "0x8086", "0x10de"

# files that belong in the card's hwmon directory rather than next to it
_HWMON_PREFIXES = ("temp", "fan", "power", "freq", "energy", "in")


def fake_drm(tmp_path, monkeypatch, *cards):
    """Build a /sys/class/drm lookalike and point ryuo_send at it.

    Each card is (name, vendor id, {filename: value}). Sensor files land in
    the card's hwmon directory, everything else next to it in `device/`.
    """
    for name, vendor, files in cards:
        dev = tmp_path / name / "device"
        hwmon = dev / "hwmon" / "hwmon3"
        hwmon.mkdir(parents=True)
        (dev / "vendor").write_text(f"{vendor}\n")
        for filename, value in files.items():
            target = hwmon if filename.startswith(_HWMON_PREFIXES) else dev
            (target / filename).write_text(f"{value}\n")
    monkeypatch.setattr(send, "_DRM_ROOT", str(tmp_path))
    monkeypatch.setattr(send, "_GPU_SYSFS", False)         # drop the cache


# ------------------------------------------------------------- Linux, by sysfs

def test_amdgpu_reports_everything(tmp_path, monkeypatch):
    """amdgpu is the one driver that fills in every field."""
    fake_drm(tmp_path, monkeypatch,
             ("card0", AMD, {"temp1_input": 61000,          # millidegrees
                             "fan1_input": 1320,            # rpm
                             "power1_average": 142_000_000,  # microwatts
                             "freq1_input": 2_400_000_000,   # hertz
                             "gpu_busy_percent": 37}))
    assert send._gpu_sysfs() == {
        "name": "AMD Graphics",
        "stats": {"hasDedicated": True, "load": 37, "temperature": 61,
                  "fan": 1320, "speed": 2400, "power": 142, "voltage": 0}}


def test_amdgpu_falls_back_to_power1_input(tmp_path, monkeypatch):
    """Newer kernels expose power1_input where older ones had the average."""
    fake_drm(tmp_path, monkeypatch,
             ("card0", AMD, {"temp1_input": 55000,
                             "power1_input": 90_000_000}))
    assert send._gpu_sysfs()["stats"]["power"] == 90


def test_intel_xe_uses_temp2(tmp_path, monkeypatch):
    """xe (kernel 6.15+) has no temp1 — temp2 is its package sensor."""
    fake_drm(tmp_path, monkeypatch,
             ("card0", INTEL, {"temp2_input": 48000, "temp3_input": 52000}))
    assert send._gpu_sysfs()["stats"]["temperature"] == 48


def test_intel_i915_uses_temp1(tmp_path, monkeypatch):
    """i915 (kernel 6.12+) starts at temp1 instead."""
    fake_drm(tmp_path, monkeypatch, ("card0", INTEL, {"temp1_input": 44000}))
    assert send._gpu_sysfs()["stats"]["temperature"] == 44


def test_intel_load_stays_zero(tmp_path, monkeypatch):
    """Neither Intel driver has a load counter we can read unprivileged."""
    fake_drm(tmp_path, monkeypatch, ("card0", INTEL, {"temp1_input": 44000}))
    assert send._gpu_sysfs()["stats"]["load"] == 0


def test_integrated_gpu_with_nothing_readable_is_not_a_gpu(tmp_path,
                                                           monkeypatch):
    """An integrated GPU gets an hwmon directory with no temperature in it.

    Reporting that as a GPU would put a permanent 0 on the panel, which looks
    exactly like a GPU that stopped updating.
    """
    fake_drm(tmp_path, monkeypatch, ("card0", INTEL, {"energy1_input": 99}))
    assert send._gpu_sysfs() == {}


def test_nvidia_is_left_to_nvidia_smi(tmp_path, monkeypatch):
    """nvidia-smi reports more than sysfs, so sysfs skips NVIDIA cards."""
    fake_drm(tmp_path, monkeypatch, ("card0", NVIDIA, {"temp1_input": 70000}))
    assert send._gpu_sysfs() == {}


def test_skips_a_card_that_reports_nothing(tmp_path, monkeypatch):
    """The first card enumerated is not necessarily the one that answers."""
    fake_drm(tmp_path, monkeypatch,
             ("card0", INTEL, {"energy1_input": 1}),
             ("card1", AMD, {"temp1_input": 59000}))
    assert send._gpu_sysfs()["stats"]["temperature"] == 59


def test_no_gpu_at_all(tmp_path, monkeypatch):
    fake_drm(tmp_path, monkeypatch)
    assert send._gpu_sysfs() == {}


def test_values_are_reread_not_cached(tmp_path, monkeypatch):
    """Only the card location is cached. The numbers must move.

    The NVIDIA path once cached its whole result for the life of the process,
    which froze every GPU field on the panel while the CPU figures next to it
    kept moving. Don't reintroduce that here.
    """
    fake_drm(tmp_path, monkeypatch, ("card0", AMD, {"temp1_input": 40000}))
    assert send._gpu_sysfs()["stats"]["temperature"] == 40
    (tmp_path / "card0" / "device" / "hwmon" / "hwmon3"
     / "temp1_input").write_text("75000\n")
    assert send._gpu_sysfs()["stats"]["temperature"] == 75


def test_unreadable_files_degrade_to_zero(tmp_path, monkeypatch):
    """A sensor that returns junk must not take the whole GPU with it."""
    fake_drm(tmp_path, monkeypatch,
             ("card0", AMD, {"temp1_input": 61000, "fan1_input": "N/A"}))
    stats = send._gpu_sysfs()["stats"]
    assert stats["temperature"] == 61
    assert stats["fan"] == 0


# ----------------------------------------------------------- source precedence

def test_nvidia_smi_wins_when_present(monkeypatch):
    """nvidia-smi reports load, clock and power, so it goes first."""
    monkeypatch.setattr(send, "_nvidia", lambda: {"name": "nvidia"})
    monkeypatch.setattr(send, "_gpu_sysfs", lambda: {"name": "sysfs"})
    monkeypatch.setattr(send, "_gpu_d3dkmt", lambda: {"name": "d3dkmt"})
    assert send._gpu()["name"] == "nvidia"


@pytest.mark.parametrize("system, expected", [("Linux", "sysfs"),
                                              ("Windows", "d3dkmt")])
def test_fallback_is_per_platform(monkeypatch, system, expected):
    monkeypatch.setattr(send, "_nvidia", lambda: {})
    monkeypatch.setattr(send, "_gpu_sysfs", lambda: {"name": "sysfs"})
    monkeypatch.setattr(send, "_gpu_d3dkmt", lambda: {"name": "d3dkmt"})
    monkeypatch.setattr(platform, "system", lambda: system)
    assert send._gpu()["name"] == expected


def test_no_source_reports_no_gpu(monkeypatch):
    """collect() turns {} into hasDedicated=False, so {} must survive."""
    monkeypatch.setattr(send, "_nvidia", lambda: {})
    monkeypatch.setattr(send, "_gpu_sysfs", lambda: {})
    monkeypatch.setattr(send, "_gpu_d3dkmt", lambda: {})
    assert send._gpu() == {}


# --------------------------------------------------------------------- Windows

def test_d3dkmt_declines_off_windows(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert send._gpu_d3dkmt() == {}


@pytest.mark.skipif(platform.system() != "Windows", reason="needs D3DKMT")
def test_d3dkmt_shape_on_windows():
    """Whatever this machine has, the shape must be right and it must not raise.

    A machine with no GPU the driver will talk about returns {}, which is a
    pass — the assertion is that nothing blows up and the fields are sane.
    """
    result = send._gpu_d3dkmt()
    assert isinstance(result, dict)
    if not result:
        pytest.skip("no adapter here reports a temperature")
    stats = result["stats"]
    assert set(stats) == {"hasDedicated", "load", "temperature", "fan",
                          "speed", "power", "voltage"}
    assert 0 < stats["temperature"] < 150       # deci-Celsius, divided by 10
    assert stats["fan"] >= 0
    assert isinstance(result["name"], str)


@pytest.mark.skipif(platform.system() != "Windows", reason="needs D3DKMT")
def test_d3dkmt_does_not_leak_adapter_handles():
    """It runs once a second forever, so the handles have to come back.

    If D3DKMTCloseAdapter stops being called, this is where you find out: the
    reads start failing once the process runs out of adapter handles.
    """
    first = send._gpu_d3dkmt()
    if not first:
        pytest.skip("no adapter here reports a temperature")
    for _ in range(300):
        last = send._gpu_d3dkmt()
    # not compared field by field: a real temperature moves between polls
    assert last and last["name"] == first["name"]


# ------------------------------------------------- this machine, for real

def test_live_gpu_is_plausible():
    """Read this machine's GPU exactly as ryuo_send does, and sanity-check it.

    The fake trees above prove the parsing; this proves the parsing matches
    the hardware in front of you. Run it on any machine, cooler or not.
    """
    result = send._gpu()
    assert isinstance(result, dict)
    if not result:
        pytest.skip("no GPU readable here (that is a valid outcome)")

    stats = result["stats"]
    assert set(stats) == {"hasDedicated", "load", "temperature", "fan",
                          "speed", "power", "voltage"}
    assert all(isinstance(v, int) for k, v in stats.items()
               if k != "hasDedicated")
    # a GPU that is powered on and readable is between freezing and melting
    assert 0 < stats["temperature"] < 150, f"implausible: {stats}"
    assert 0 <= stats["load"] <= 100
    assert 0 <= stats["fan"] < 20000
    assert isinstance(result["name"], str)


def _describe(source: str, result: dict) -> str:
    if not result:
        return f"{source:<14} --"
    s = result["stats"]
    return (f"{source:<14} {result['name'] or '(unnamed)'}\n"
            f"{'':<14} temp={s['temperature']}C load={s['load']}% "
            f"fan={s['fan']}rpm clock={s['speed']}MHz power={s['power']}W")


if __name__ == "__main__":
    # Run this file directly (no pytest, no cooler) to see what each source
    # reports on this machine and which one ryuo_send would actually use:
    #
    #     python tests/test_gpu.py
    #
    # A source that isn't available here prints "--", which is expected: sysfs
    # is Linux-only, D3DKMT is Windows-only, nvidia-smi needs an NVIDIA card.
    print(f"{platform.system()}, {platform.machine()}\n")
    print(_describe("nvidia-smi", send._nvidia()))
    print(_describe("sysfs", send._gpu_sysfs()))
    print(_describe("d3dkmt", send._gpu_d3dkmt()))
    print(_describe("ryuo_send uses", send._gpu()))
    try:
        import psutil
    except ImportError:
        print("\ncpu temperature  (pip install psutil to check)")
    else:
        cur, package = send._cpu_temp(psutil)
        print(f"\ncpu            temp={cur:.0f}C package={package:.0f}C"
              + ("   <- 0 is expected on Windows, see the README"
                 if not cur else ""))
