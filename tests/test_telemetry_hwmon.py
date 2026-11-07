# SPDX-License-Identifier: GPL-3.0-or-later
from fixtures.sysfs_builder import SysfsBuilder
from ryuo_screen.models import SensorRef
from ryuo_screen.telemetry.hwmon import HwmonProvider
from ryuo_screen.telemetry.sysfs import Sysfs


def _board(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    device = fake.root / "devices/platform/nct6775.656"
    fake.link(device / "driver", fake.root / "bus/platform/drivers/nct6775")
    chip = fake.hwmon(device, 3, "nct6799", {
        "fan1": (1190, "CPU Fan"),
        "fan2": (650, "Chassis Fan 1"),
        "temp1": (77000, None),
        "temp2": (37000, "SYSTIN"),
    })
    return fake, chip


def test_board_auto_prefers_systin_and_fans_remain_stable_after_renumber(tmp_path):
    fake, chip = _board(tmp_path)
    provider = HwmonProvider(Sysfs(fake.root))
    sample = provider.sample().measurements
    fans = {d.label: d for d in provider.probe() if d.unit == "RPM"}

    assert sample["motherboard.temperature"].value == 37
    assert set(fans) == {"CPU Fan", "Chassis Fan 1"}
    assert fans["CPU Fan"].source.endswith("/fan1_input")
    assert fans["CPU Fan"].ref.device == "platform/nct6775.656/nct6799"
    assert fans["CPU Fan"].ref.channel == "fan1"
    assert sample[fans["CPU Fan"].measurement_id].value == 1190
    assert sample[fans["Chassis Fan 1"].measurement_id].value == 650
    assert all(d.measurement_id.startswith("fan.") and d.measurement_id.endswith(".rpm")
               for d in fans.values())

    (fake.root / "class/hwmon/hwmon3").unlink()
    renumbered = chip.rename(chip.with_name("hwmon7"))
    fake.link(fake.root / "class/hwmon/hwmon7", renumbered)

    second = provider.sample().measurements
    assert {key: m.ref for key, m in second.items()} == {key: m.ref for key, m in sample.items()}
    assert second[fans["CPU Fan"].measurement_id].value == 1190
    assert second["motherboard.temperature"].value == 37


def test_manual_board_sensor_is_exact_and_never_falls_back(tmp_path):
    fake, chip = _board(tmp_path)
    ref = SensorRef("hwmon", "platform/nct6775.656/nct6799", "temp1")
    provider = HwmonProvider(Sysfs(fake.root), motherboard_ref=ref)
    sample = provider.sample().measurements["motherboard.temperature"]
    assert sample.ref == ref
    assert sample.value == 77

    (chip / "temp1_input").unlink()
    sample = provider.sample().measurements["motherboard.temperature"]
    assert sample.ref == ref
    assert sample.value is None and not sample.available and sample.error


def test_gpu_temperature_is_not_an_auto_motherboard_candidate(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    fake.hwmon(fake.pci(), 2, "amdgpu", {"temp1": (76000, "junction")})
    sample = HwmonProvider(Sysfs(fake.root)).sample().measurements["motherboard.temperature"]
    assert not sample.available and sample.value is None and sample.error
