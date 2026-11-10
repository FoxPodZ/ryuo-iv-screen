# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from fixtures.sysfs_builder import SysfsBuilder
from ryuo_screen.telemetry.cpu import CpuProvider
from ryuo_screen.telemetry.sysfs import Sysfs


@pytest.fixture
def cpu(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    proc = tmp_path / "proc"
    proc.mkdir()
    return fake, proc, CpuProvider(Sysfs(fake.root), proc_root=proc, clock=lambda: 100.5)


def test_cpu_load_uses_counter_deltas_and_excludes_iowait_and_guest(cpu):
    _, proc, provider = cpu
    stat = proc / "stat"
    stat.write_text("cpu 200 0 100 700 0 0 0 0 10 0\n")
    first = provider.sample().measurements["cpu.load"]
    assert not first.available and first.value is None and first.error
    # 20 active, 70 idle, 10 iowait; guest time is already included in user.
    stat.write_text("cpu 210 0 110 770 10 0 0 0 19 0\n")
    provider.probe()  # Discovery must not consume the sampling baseline.
    load = provider.sample().measurements["cpu.load"]
    assert load.value == 20
    assert load.unit == "%"
    assert load.sampled_at == 100.5

    stat.write_text("cpu 5 0 4 8\n")
    assert not provider.sample().measurements["cpu.load"].available


def test_cpu_frequency_averages_online_cpufreq_and_falls_back_to_cpuinfo(cpu):
    fake, proc, provider = cpu
    cpu_dir = fake.root / "devices/system/cpu"
    for index, khz in enumerate((2100000, 3300000, 900000)):
        core = cpu_dir / ("cpu%d" % index)
        (core / "cpufreq").mkdir(parents=True)
        (core / "cpufreq/scaling_cur_freq").write_text(str(khz))
        if index:
            (core / "online").write_text("1" if index == 1 else "0")

    assert provider.sample().measurements["cpu.frequency"].value == 2700

    (cpu_dir / "cpu1/cpufreq/scaling_cur_freq").unlink()
    assert provider.sample().measurements["cpu.frequency"].value == 2100

    (cpu_dir / "cpu0/cpufreq/scaling_cur_freq").unlink()
    (proc / "cpuinfo").write_text(
        "processor: 0\ncpu MHz: 2000.0\n\nprocessor: 1\ncpu MHz: 3400.0\n\n"
        "processor: 2\ncpu MHz: 900.0\n"
    )
    assert provider.sample().measurements["cpu.frequency"].value == 2700
    frequency = next(d for d in provider.probe() if d.measurement_id == "cpu.frequency")
    assert frequency.source == str(proc / "cpuinfo")


def test_cpu_temperatures_prefer_tdie_and_tctl_over_unrelated_hwmon(cpu):
    fake, _, provider = cpu
    gpu = fake.pci()
    fake.hwmon(gpu, 0, "amdgpu", {"temp1": (82000, "edge"), "power1": (200000000, None)})
    fake.hwmon(gpu.parent, 3, "k10temp", {"temp1": (51000, "Tctl"), "temp2": (45500, "Tdie")})
    sample = provider.sample().measurements

    assert sample["cpu.temperature"].value == 45.5
    assert sample["cpu.temperature.package"].value == 51
    assert sample["cpu.temperature"].unit == "°C"
    assert not sample["cpu.power"].available
    assert "cpu.voltage" not in sample


def test_cpu_power_prefers_average_then_input_without_losing_temperature(cpu):
    fake, _, provider = cpu
    chip = fake.hwmon(
        fake.root / "devices/platform/zenpower", 4, "zenpower",
        {"temp1": (51000, "Tctl"), "power2": (43750000, "Package")},
    )
    average = chip / "power2_average"
    average.write_text("41400000")

    assert provider.sample().measurements["cpu.power"].value == pytest.approx(41.4)
    power = next(d for d in provider.probe() if d.measurement_id == "cpu.power")
    assert power.source.endswith("/power2_average")
    average.unlink()

    assert provider.sample().measurements["cpu.power"].value == pytest.approx(43.75)
    (chip / "power2_input").unlink()

    sample = provider.sample().measurements
    assert sample["cpu.temperature"].value == 51
    assert sample["cpu.power"].value is None
    assert not sample["cpu.power"].available and sample["cpu.power"].error


@pytest.mark.parametrize("package_label", ["Package id 0", "Physical id 0"])
def test_coretemp_prefers_package_over_other_temperatures(cpu, package_label):
    fake, _, provider = cpu
    fake.hwmon(fake.root / "devices/platform/coretemp.0", 3, "coretemp", {
        "temp1": (38000, "Core 0"), "temp2": (47000, package_label),
    })
    sample = provider.sample().measurements
    assert sample["cpu.temperature"].value == sample["cpu.temperature.package"].value == 47


def test_coretemp_keeps_core_temperature_when_package_sensor_disappears(cpu):
    fake, _, provider = cpu
    chip = fake.hwmon(fake.root / "devices/platform/coretemp.0", 3, "coretemp", {
        "temp1": (38000, "Core 0"), "temp2": (47000, "Package id 0"),
    })
    assert provider.sample().measurements["cpu.temperature.package"].value == 47
    (chip / "temp2_input").unlink()

    sample = provider.sample().measurements
    assert sample["cpu.temperature"].value == 38
    package = sample["cpu.temperature.package"]
    assert not package.available and package.value is None and package.error


def test_unlabeled_acpitz_is_not_a_cpu_or_package_temperature(cpu):
    fake, _, provider = cpu
    fake.hwmon(fake.root / "devices/virtual/thermal/thermal_zone0", 3, "acpitz", {
        "temp1": (29000, None),
    })

    sample = provider.sample().measurements
    for key in ("cpu.temperature", "cpu.temperature.package"):
        reading = sample[key]
        assert not reading.available and reading.value is None and reading.error


def test_cpu_labeled_acpitz_can_only_supply_general_cpu_temperature(cpu):
    fake, _, provider = cpu
    fake.hwmon(fake.root / "devices/virtual/thermal/thermal_zone0", 3, "acpitz", {
        "temp1": (29000, None), "temp2": (43000, "CPU"),
    })

    sample = provider.sample().measurements
    assert sample["cpu.temperature"].value == 43
    assert not sample["cpu.temperature.package"].available


def test_cpu_package_power_uses_energy_delta_and_handles_counter_wrap(cpu):
    fake, proc, _ = cpu
    cap = fake.root / "class/powercap/intel-rapl"
    package = cap / "intel-rapl:0"
    package.mkdir(parents=True)
    (package / "name").write_text("package-0")
    (package / "max_energy_range_uj").write_text("1000000000")
    energy = package / "energy_uj"
    energy.write_text("990000000")
    now = [10.0]
    provider = CpuProvider(Sysfs(fake.root), proc_root=proc, clock=lambda: now[0])

    first = provider.sample().measurements["cpu.power"]
    assert not first.available and "second" in first.error
    now[0] = 10.5
    energy.write_text("15000000")
    provider.probe()

    # 10 J until wrap, then 15 J, over half a second.
    power = provider.sample().measurements["cpu.power"]
    assert power.value == 50
    assert power.unit == "W"
    assert power.sampled_at == 10.5
    assert not provider.sample().measurements["cpu.power"].available
