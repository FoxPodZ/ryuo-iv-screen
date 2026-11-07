# SPDX-License-Identifier: GPL-3.0-or-later
from types import SimpleNamespace

from fixtures.amd_rx7900xtx import rx7900xtx
from fixtures.sysfs_builder import SysfsBuilder
import ryuo_proto as proto
import ryuo_send
from ryuo_screen.models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot
from ryuo_screen.telemetry.amd import AmdGpuProvider
from ryuo_screen.telemetry.collector import TelemetryCollector
from ryuo_screen.telemetry.cpu import CpuProvider
from ryuo_screen.telemetry.hwmon import HwmonProvider
from ryuo_screen.telemetry.sysfs import Sysfs


class _Provider:
    def __init__(self, provider_id, metrics):
        self.provider_id = provider_id
        self.metrics = metrics
        self.probes = 0

    def probe(self):
        self.probes += 1
        return tuple(
            SensorDescriptor(SensorRef(self.provider_id, "device", key),
                             key, label, unit, source="/test/" + key)
            for key, (_, label, unit) in self.metrics.items()
        )

    def sample(self):
        return TelemetrySnapshot({
            key: Measurement(SensorRef(self.provider_id, "device", key),
                             key, value, unit, 5, available=value is not None,
                             error="Device disappeared" if value is None else None)
            for key, (value, _, unit) in self.metrics.items()
        }, 5)


def test_provider_exception_keeps_other_measurements():
    class BrokenProvider(_Provider):
        def probe(self):
            raise OSError("probe failed")

        def sample(self):
            raise RuntimeError("read failed")

    cpu = _Provider("cpu", {"cpu.load": (32, "CPU load", "%")})
    collector = TelemetryCollector([BrokenProvider("bad", {}), cpu])

    sample = collector.sample()
    assert sample.measurements["cpu.load"].value == 32
    assert "read failed" in sample.errors["bad"]
    assert {d.measurement_id for d in collector.catalog()} == {"cpu.load"}


def test_catalog_reports_source_and_unavailable_reason():
    board = _Provider("hwmon", {"motherboard.temperature": (None, "Board", "°C")})
    collector = TelemetryCollector([board])

    sample = collector.sample()
    assert sample.measurements["motherboard.temperature"].value is None
    descriptor, = collector.catalog()
    assert descriptor.source == "/test/motherboard.temperature"
    assert not descriptor.available and descriptor.error == "Device disappeared"


def test_probe_is_cached_for_sixty_seconds_and_invalidated_on_demand():
    cpu = _Provider("cpu", {"cpu.load": (32, "CPU load", "%")})
    now = [0.0]
    collector = TelemetryCollector([cpu], clock=lambda: now[0])

    collector.sample()
    now[0] = 59.99
    collector.catalog()
    collector.sample()
    assert cpu.probes == 1
    now[0] = 60
    collector.sample()
    assert cpu.probes == 2
    collector.invalidate()
    collector.catalog()
    assert cpu.probes == 3


def test_pc_info_keys_exactly_match_existing_contract():
    collector = TelemetryCollector([])
    result = collector.to_pc_info(TelemetrySnapshot({}, 42.5))
    defaults = proto.pc_info(timestamp_ms=42500)
    defaults["gpu"]["hasDedicated"] = False

    assert result == defaults


def test_vram_stays_in_api_but_is_not_fake_rpm_widget():
    gpu = _Provider("amd", {"gpu.vram.used": (1073741824, "VRAM used", "B")})
    collector = TelemetryCollector([gpu])

    sample = collector.sample()
    assert sample.measurements["gpu.vram.used"].value == 1073741824
    assert collector.catalog()[0].measurement_id == "gpu.vram.used"
    assert collector.to_pc_info(sample)["fans"] == []


def test_gpu_and_fan_values_preserve_existing_protocol_fields():
    gpu = _Provider("amd", {
        "gpu.load": (42, "GPU load", "%"), "gpu.temperature": (44.7, "GPU temperature", "°C"),
        "gpu.clock.core": (2410, "Core clock", "MHz"), "gpu.power": (94.75, "GPU power", "W"),
        "gpu.fan": (1200, "GPU fan", "RPM"),
    })
    cpu = _Provider("cpu", {
        "cpu.load": (35.9, "CPU load", "%"), "cpu.voltage": (1.147, "CPU voltage", "V"),
        "cpu.temperature": (46.6, "CPU", "°C"),
    })
    board = _Provider("hwmon", {
        "fan.a.rpm": (1230, "CPU Fan", "RPM"), "fan.b.rpm": (None, "Chassis Fan", "RPM"),
        "motherboard.temperature": (33, "Board", "°C"),
    })
    collector = TelemetryCollector([gpu, cpu, board])
    result = collector.to_pc_info(collector.sample(), extra_readouts={"Coolant": 319})

    assert result["gpu"] == {
        "hasDedicated": True, "load": 42, "temperature": 44, "speed": 2410,
        "power": 94, "fan": 1200, "voltage": 0,
    }
    assert result["cpu"] == {
        "load": 35, "usage": 35, "temperature": 47, "temperaturePackage": 0,
        "speedAverage": 0, "power": 0, "voltage": 1.147,
    }
    assert result["motherboard"] == {"temperature": 33, "chipsetTemperature": 0}
    assert result["fans"] == [
        {"onBoard": True, "name": "CPU Fan", "value": 1230},
        {"onBoard": True, "name": "Chassis Fan", "value": 0},
        {"onBoard": True, "name": "Coolant", "value": 319},
    ]
    assert proto.fan_item(result["fans"][-1]["name"]) == "Fan Speed Coolant"


def test_gpu_selection_never_fills_an_unavailable_field_from_another_gpu():
    amd = _Provider("amd", {"gpu.load": (42, "GPU load", "%"), "gpu.fan": (None, "Fan", "RPM")})
    nvidia = _Provider("nvidia", {
        "gpu.load": (89, "GPU load", "%"), "gpu.fan": (34, "Fan", "%"),
        "gpu.temperature": (57, "GPU temperature", "°C"),
    })
    cpu = _Provider("cpu", {"cpu.load": (16, "CPU load", "%")})

    auto = TelemetryCollector([amd, nvidia, cpu]).sample().measurements
    assert auto["gpu.load"].value == 42
    assert auto["gpu.fan"].value is None
    assert "gpu.temperature" not in auto
    assert auto["cpu.load"].value == 16

    preferred = TelemetryCollector([amd, nvidia, cpu], preferred_gpu_provider="nvidia")
    assert preferred.sample().measurements["gpu.load"].value == 89
    assert {d.ref.provider for d in preferred.catalog()} == {"amd", "nvidia", "cpu"}

    amd.metrics = {}
    assert TelemetryCollector([amd, nvidia]).sample().measurements["gpu.load"].value == 89
    strict = TelemetryCollector([amd, nvidia], preferred_gpu_provider="amd")
    assert not strict.sample().measurements


def _psutil():
    return SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(total=8 * 1024**3, used=2 * 1024**3, percent=25),
        disk_usage=lambda root: SimpleNamespace(total=100 * 1024**3, used=20 * 1024**3, percent=20),
        cpu_freq=lambda: SimpleNamespace(current=3300),
        cpu_percent=lambda: 17,
        sensors_temperatures=lambda: {"k10temp": [
            SimpleNamespace(label="Tdie", current=41.4), SimpleNamespace(label="Tctl", current=47.6)
        ]},
        sensors_fans=lambda: {"legacy": [SimpleNamespace(label="Legacy Fan", current=999)]},
    )


def test_linux_collect_maps_native_amd_and_preserves_supplied_gpu_and_psutil_stats(tmp_path, monkeypatch):
    fake = SysfsBuilder(tmp_path / "sys")
    rx7900xtx(fake)
    fake.hwmon(fake.root / "devices/platform/nct6775.656", 9, "nct6799", {
        "temp1": (31000, "SYSTIN"), "fan1": (730, "Chassis Fan"),
    })
    proc = tmp_path / "proc"
    proc.mkdir()
    sysfs = Sysfs(fake.root)
    monkeypatch.setattr(ryuo_send.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ryuo_send, "_LINUX_TELEMETRY", TelemetryCollector([
        CpuProvider(sysfs, proc_root=proc), HwmonProvider(sysfs), AmdGpuProvider(sysfs),
    ]))

    result = ryuo_send.collect(_psutil(), {}, {"Coolant": 27})
    assert result["cpu"]["load"] == 17
    assert result["cpu"]["temperaturePackage"] == 48
    assert result["cpu"]["speedAverage"] == 3300
    assert result["memory"]["total"] == 8192
    assert result["disk"]["used"] == 20
    assert result["gpu"]["speed"] == 2365
    assert result["gpu"]["fan"] == 1100
    assert result["motherboard"]["temperature"] == 31
    assert {"onBoard": True, "name": "Chassis Fan", "value": 730} in result["fans"]
    assert result["fans"][-1] == {"onBoard": True, "name": "Coolant", "value": 27}

    supplied = {"stats": {"hasDedicated": True, "load": 72, "temperature": 43, "fan": 43,
                          "speed": 2900, "power": 105, "voltage": 0}}
    assert ryuo_send.collect(_psutil(), supplied)["gpu"] == supplied["stats"]


def test_windows_collect_keeps_existing_psutil_behavior(monkeypatch):
    monkeypatch.setattr(ryuo_send.platform, "system", lambda: "Windows")
    psutil = _psutil()

    def disk_usage(root):
        assert root == "C:\\"
        return SimpleNamespace(total=100 * 1024**3, used=20 * 1024**3, percent=20)

    psutil.disk_usage = disk_usage
    assert ryuo_send._cpu_temp(psutil) == (41.4, 47.6)
    result = ryuo_send.collect(psutil, {}, {"Coolant": 27})
    assert result["cpu"]["temperature"] == 41
    assert result["cpu"]["temperaturePackage"] == 48
    assert result["cpu"]["load"] == 17
    assert not result["gpu"]["hasDedicated"]
    assert result["fans"] == [
        {"onBoard": True, "name": "Legacy Fan", "value": 999},
        {"onBoard": True, "name": "Coolant", "value": 27},
    ]


def test_disappeared_fan_keeps_unavailable_reading_until_reprobe(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    chip = fake.hwmon(fake.root / "devices/platform/nct6775.656", 9, "nct6799", {
        "fan1": (730, None),
    })
    collector = TelemetryCollector([HwmonProvider(Sysfs(fake.root))])
    initial = collector.sample()
    fan, = [key for key in initial.measurements if key.startswith("fan.")]
    # Existing screens configured for psutil's unlabeled fan use the chip name.
    assert collector.to_pc_info(initial)["fans"] == [
        {"onBoard": True, "name": "nct6799", "value": 730},
    ]

    (chip / "fan1_input").unlink()
    disappeared = collector.sample()
    assert not disappeared.measurements[fan].available
    assert disappeared.measurements[fan].value is None
    assert disappeared.measurements[fan].error
    assert collector.to_pc_info(disappeared)["fans"][0]["value"] == 0
    collector.invalidate()
    assert fan not in collector.sample().measurements


def test_unavailable_explicit_cpu_usage_does_not_become_load():
    provider = _Provider("cpu", {"cpu.load": (32, "CPU load", "%"),
                                 "cpu.usage": (None, "CPU usage", "%")})
    collector = TelemetryCollector([provider])
    assert collector.to_pc_info(collector.sample())["cpu"]["usage"] == 0
