# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise AMD telemetry against an on-disk sysfs fixture."""

import os
from pathlib import Path

import pytest

from fixtures.amd_rx7900xtx import RX_7900_XTX_BDF, rx7900xtx
from fixtures.sysfs_builder import SysfsBuilder
from ryuo_screen.telemetry.amd import AmdGpuProvider
from ryuo_screen.telemetry.sysfs import Sysfs, enumerate_hwmon


def test_rx7900xtx_measurements_have_expected_values_and_units(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    rx7900xtx(fake)
    provider = AmdGpuProvider(Sysfs(fake.root))
    expected = {
        "gpu.temperature": (45.4, "°C"),
        "gpu.load": (42, "%"),
        "gpu.clock.core": (2365, "MHz"),
        "gpu.clock.memory": (1250, "MHz"),
        "gpu.vram.used": (1610612736, "B"),
        "gpu.vram.total": (25769803776, "B"),
        "gpu.power": (108.75, "W"),
        "gpu.fan": (1100, "RPM"),
    }

    snapshot = provider.sample()
    catalog = {entry.measurement_id: entry for entry in provider.probe()}

    assert not snapshot.errors
    assert snapshot.measurements.keys() == catalog.keys() == expected.keys()
    for measurement_id, (value, unit) in expected.items():
        reading = snapshot.measurements[measurement_id]
        descriptor = catalog[measurement_id]
        if unit == "B":
            assert isinstance(reading.value, int) and reading.value == value
        else:
            assert reading.value == pytest.approx(value)
        assert reading.unit == descriptor.unit == unit
        assert reading.sampled_at == snapshot.sampled_at
        assert reading.available and descriptor.available
        assert reading.error is None and descriptor.error is None
        assert reading.ref == descriptor.ref
        assert descriptor.ref.provider == provider.provider_id == "amd"
        assert descriptor.ref.device == descriptor.metadata["bdf"] == RX_7900_XTX_BDF
        assert descriptor.metadata["selected"] is True
        assert descriptor.metadata["name"] == "AMD Radeon RX 7900 XTX"
        assert descriptor.source
    assert catalog["gpu.power"].source.endswith("/power1_average")
    assert catalog["gpu.fan"].metadata["source_label"] == "GPU fan"


def test_auto_selects_discrete_gpu_with_largest_vram(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    igpu = fake.pci(bdf="0000:01:00.0", device="0x164e", card="card0")
    dgpu, _ = rx7900xtx(fake)
    small_dgpu = fake.pci(bdf="0000:02:00.0", device="0x73bf", card="card2")
    (igpu / "mem_info_vram_total").write_text("536870912", encoding="ascii")
    (small_dgpu / "mem_info_vram_total").write_text("8589934592", encoding="ascii")
    (dgpu / "gpu_busy_percent").write_text("91", encoding="ascii")
    provider = AmdGpuProvider(Sysfs(fake.root))

    catalog = provider.probe()
    sample = provider.sample()

    assert len(catalog) == 24
    assert len({entry.ref.stable_id for entry in catalog}) == 24
    assert {entry.metadata["bdf"] for entry in catalog} == {
        "0000:01:00.0", "0000:02:00.0", RX_7900_XTX_BDF,
    }
    assert {entry.metadata["bdf"] for entry in catalog if entry.metadata["selected"]} == {
        RX_7900_XTX_BDF,
    }
    assert sample.measurements["gpu.load"].value == 91
    assert {reading.ref.device for reading in sample.measurements.values()} == {RX_7900_XTX_BDF}


def test_auto_uses_bdf_order_for_equal_vram_and_puts_unreadable_vram_last(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    for bdf, vram in (
        ("0000:05:00.0", "8589934592"),
        ("0000:01:00.0", "N/A"),
        ("0000:04:00.0", "8589934592"),
    ):
        gpu = fake.pci(bdf=bdf)
        (gpu / "mem_info_vram_total").write_text(vram, encoding="ascii")

    sample = AmdGpuProvider(Sysfs(fake.root)).sample()

    assert sample.measurements["gpu.vram.total"].ref.device == "0000:04:00.0"
    assert sample.measurements["gpu.vram.total"].value == 8589934592


def test_manual_bdf_selects_requested_gpu(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    rx7900xtx(fake)
    requested_bdf = "0000:05:00.0"
    gpu = fake.pci(bdf=requested_bdf, device="0x164e", card="card0")
    (gpu / "gpu_busy_percent").write_text("17", encoding="ascii")
    provider = AmdGpuProvider(Sysfs(fake.root), selected_bdf=requested_bdf)

    assert {entry.metadata["bdf"] for entry in provider.probe() if entry.metadata["selected"]} == {
        requested_bdf,
    }
    measurements = provider.sample().measurements
    assert measurements["gpu.load"].value == 17
    assert {reading.ref.device for reading in measurements.values()} == {requested_bdf}


@pytest.mark.parametrize("requested_bdf", ["0000:99:00.0", "0000:05:00.0"])
def test_unavailable_manual_bdf_does_not_fall_back(tmp_path, requested_bdf):
    fake = SysfsBuilder(tmp_path / "sys")
    rx7900xtx(fake)
    unbound = fake.pci(bdf="0000:05:00.0")
    (unbound / "driver").unlink()
    provider = AmdGpuProvider(Sysfs(fake.root), selected_bdf=requested_bdf)

    catalog = provider.probe()
    sample = provider.sample()

    assert len(catalog) == 8
    assert not any(entry.metadata["selected"] for entry in catalog)
    assert not sample.measurements
    assert requested_bdf in sample.errors["amd"]


def test_non_amd_and_non_display_pci_are_ignored(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    fake.pci(bdf="0000:01:00.0", vendor="0x10de")
    fake.pci(bdf="0000:02:00.0", class_code="0x040300")
    fake.pci(bdf="0000:04:00.0", driver="vfio-pci")
    gpu = fake.pci(bdf="0000:05:00.0", class_code="0x038000")
    (gpu / "gpu_busy_percent").write_text("12", encoding="ascii")
    provider = AmdGpuProvider(Sysfs(fake.root))

    assert {entry.metadata["bdf"] for entry in provider.probe()} == {"0000:05:00.0"}
    assert provider.sample().measurements["gpu.load"].value == 12


def test_empty_sysfs_is_reported_without_measurements(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    provider = AmdGpuProvider(Sysfs(fake.root))

    assert not provider.probe()
    snapshot = provider.sample()
    assert not snapshot.measurements
    assert snapshot.errors["amd"]


def test_missing_optional_readings_leave_only_those_measurements_unavailable(tmp_path, monkeypatch):
    fake = SysfsBuilder(tmp_path / "sys")
    gpu, chip = rx7900xtx(fake)
    (gpu / "mem_info_vram_used").unlink()
    (chip / "freq5_label").unlink()
    (chip / "fan1_input").write_text("broken", encoding="ascii")
    original_open = os.open

    def deny_gpu_busy(path, *args, **kwargs):
        if Path(path).name == "gpu_busy_percent":
            raise PermissionError("busy counter denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", deny_gpu_busy)
    provider = AmdGpuProvider(Sysfs(fake.root))
    catalog = {entry.measurement_id: entry for entry in provider.probe()}
    measurements = provider.sample().measurements

    assert {key for key, value in measurements.items() if value.available} == {
        "gpu.temperature", "gpu.clock.core", "gpu.vram.total", "gpu.power",
    }
    for key in ("gpu.load", "gpu.vram.used", "gpu.clock.memory", "gpu.fan"):
        assert not catalog[key].available
        assert measurements[key].value is None
        assert measurements[key].error
        assert catalog[key].error
    assert "busy counter denied" in measurements["gpu.load"].error


@pytest.mark.parametrize("junction, expected", [("62700", 62.7), ("invalid", 54.3)])
def test_temperature_falls_back_to_first_valid_channel(tmp_path, junction, expected):
    fake = SysfsBuilder(tmp_path / "sys")
    _, chip = rx7900xtx(fake)
    (chip / "temp1_input").write_text("N/A", encoding="ascii")
    (chip / "temp2_input").write_text(junction, encoding="ascii")

    sample = AmdGpuProvider(Sysfs(fake.root)).sample()

    assert sample.measurements["gpu.temperature"].value == pytest.approx(expected)


def test_power_falls_back_to_instantaneous_reading(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    _, chip = rx7900xtx(fake)
    (chip / "power1_average").unlink()
    provider = AmdGpuProvider(Sysfs(fake.root))

    assert provider.sample().measurements["gpu.power"].value == pytest.approx(113)
    power = next(entry for entry in provider.probe() if entry.measurement_id == "gpu.power")
    assert power.source.endswith("/power1_input")


def test_power_can_be_read_from_amdgpu_chip_with_only_average(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    gpu = fake.pci()
    chip = fake.hwmon(gpu, 4, "amdgpu", {})
    (chip / "power1_average").write_text("22750000", encoding="ascii")
    provider = AmdGpuProvider(Sysfs(fake.root))

    assert provider.sample().measurements["gpu.power"].value == pytest.approx(22.75)


def test_clock_uses_only_labeled_hwmon_or_active_dpm_values(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    gpu, chip = rx7900xtx(fake)
    (chip / "freq3_label").unlink()
    (chip / "freq5_label").write_text("MEM", encoding="ascii")
    (gpu / "pp_dpm_sclk").write_text("S: 18Mhz *\n0: 500Mhz\n1: 2350Mhz\n", encoding="ascii")
    (gpu / "pp_dpm_mclk").write_text("0: 96Mhz *\n1: 1250Mhz\n", encoding="ascii")
    provider = AmdGpuProvider(Sysfs(fake.root))

    sample = provider.sample()
    assert sample.measurements["gpu.clock.core"].value == 18
    assert sample.measurements["gpu.clock.memory"].value == 1250

    (gpu / "pp_dpm_sclk").write_text("0: 500Mhz\n1: 2350Mhz\n", encoding="ascii")
    assert not provider.sample().measurements["gpu.clock.core"].available


def test_missing_product_name_falls_back_to_pci_device_id(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    gpu, _ = rx7900xtx(fake)
    (gpu / "product_name").unlink()
    provider = AmdGpuProvider(Sysfs(fake.root))

    assert {entry.metadata["name"] for entry in provider.probe()} == {"AMD GPU (PCI device 0x744c)"}
    assert provider.sample().measurements["gpu.load"].value == 42


@pytest.mark.parametrize("attribute", ["uevent", "modalias"])
def test_pci_id_fallback_uses_other_sysfs_attributes_when_device_is_missing(tmp_path, attribute):
    fake = SysfsBuilder(tmp_path / "sys")
    gpu, _ = rx7900xtx(fake)
    (gpu / "product_name").unlink()
    (gpu / "device").unlink()
    contents = {
        "uevent": "DRIVER=amdgpu\nPCI_ID=1002:744C\n",
        "modalias": "pci:v00001002d0000744Csv00001002sd00000E3Abc03sc00i00\n",
    }
    (gpu / attribute).write_text(contents[attribute], encoding="ascii")

    catalog = AmdGpuProvider(Sysfs(fake.root)).probe()

    assert {entry.metadata["name"] for entry in catalog} == {"AMD GPU (PCI device 0x744c)"}


@pytest.mark.parametrize("hwmon_under_drm", [False, True])
def test_hwmon_renumber_does_not_change_gpu_identity(tmp_path, hwmon_under_drm):
    def read(root, index, card):
        fake = SysfsBuilder(root)
        _, hwmon = rx7900xtx(fake, index=index, card=card, hwmon_under_drm=hwmon_under_drm)
        target = (hwmon / "device").resolve()
        if hwmon_under_drm:
            assert target.parts[-2:] == ("drm", card)
        sysfs = Sysfs(fake.root)
        chip, = enumerate_hwmon(sysfs)
        provider = AmdGpuProvider(sysfs)
        return provider.probe(), provider.sample(), {channel.ref for channel in chip.channels}

    first_catalog, first_sample, first_channels = read(tmp_path / "first", 2, "card1")
    next_catalog, next_sample, next_channels = read(tmp_path / "next", 9, "card0")

    assert first_channels == next_channels
    assert {entry.ref for entry in first_catalog} == {entry.ref for entry in next_catalog}
    assert {entry.ref.device for entry in next_catalog} == {RX_7900_XTX_BDF}
    assert {
        key: (entry.ref, entry.value) for key, entry in first_sample.measurements.items()
    } == {
        key: (entry.ref, entry.value) for key, entry in next_sample.measurements.items()
    }
    assert next_sample.measurements["gpu.temperature"].value == pytest.approx(45.4)
    assert next_sample.measurements["gpu.power"].value == pytest.approx(108.75)
