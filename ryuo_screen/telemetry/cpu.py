# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux CPU telemetry from procfs, cpufreq and CPU hwmon chips."""

import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

from ..models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot
from .sysfs import HwmonChip, Sysfs, enumerate_hwmon

_CPUFREQ = Path("devices/system/cpu")
_CPU = re.compile(r"cpu[0-9]+")
_POWER = re.compile(r"power([0-9]+)_(average|input)")
_POWERCAP = Path("class/powercap")
_RAPL_DRIVERS = ("intel-rapl", "amd-rapl")
_RAPL_ZONE = re.compile(r"(?:intel|amd)-rapl:[0-9]+")
_TEMP_CHIPS = ("k10temp", "zenpower", "coretemp", "acpitz")
_METRICS = {
    "cpu.load": ("CPU load", "%"),
    "cpu.frequency": ("CPU frequency", "MHz"),
    "cpu.temperature": ("CPU temperature", "°C"),
    "cpu.temperature.package": ("CPU package temperature", "°C"),
    "cpu.power": ("CPU power", "W"),
}


@dataclass(frozen=True)
class _Reading:
    value: Optional[float] = None
    source: Optional[Path] = None
    error: Optional[str] = None


class CpuProvider:
    provider_id = "cpu"

    def __init__(
        self, sysfs: Sysfs, proc_root: Path = Path("/proc"),
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._sysfs = sysfs
        self._proc_root = Path(proc_root)
        self._clock = clock or time.time
        self._elapsed_clock = clock or time.monotonic
        self._previous: Optional[Tuple[int, int]] = None
        self._previous_energy: Optional[Tuple[Path, float, float]] = None

    def probe(self) -> Sequence[SensorDescriptor]:
        return tuple(
            SensorDescriptor(
                self._ref(key), key, _METRICS[key][0], _METRICS[key][1],
                available=reading.value is not None,
                source=str(reading.source) if reading.source is not None else None,
                error=reading.error,
            )
            for key, reading in self._readings(update_baseline=False).items()
        )

    def sample(self) -> TelemetrySnapshot:
        sampled_at = self._clock()
        return TelemetrySnapshot({
            key: Measurement(
                self._ref(key), key, reading.value, _METRICS[key][1], sampled_at,
                available=reading.value is not None, error=reading.error,
            )
            for key, reading in self._readings(update_baseline=True).items()
        }, sampled_at)

    def _ref(self, key: str) -> SensorRef:
        return SensorRef(self.provider_id, "host", key)

    def _readings(self, update_baseline: bool) -> Dict[str, _Reading]:
        chips = sorted(
            (chip for chip in enumerate_hwmon(self._sysfs) if chip.name in _TEMP_CHIPS),
            key=lambda chip: (_TEMP_CHIPS.index(chip.name), chip.device_id),
        )
        power = self._power(chips)
        if power.value is None:
            power = self._package_power(update_baseline) or power
        elif update_baseline:
            self._previous_energy = None
        return {
            "cpu.load": self._load(update_baseline),
            "cpu.frequency": self._frequency(),
            "cpu.temperature": self._temperature(chips, package=False),
            "cpu.temperature.package": self._temperature(chips, package=True),
            "cpu.power": power,
        }

    def _load(self, update_baseline: bool) -> _Reading:
        path = self._proc_root / "stat"
        try:
            with path.open(encoding="ascii") as stat:
                fields = stat.readline().split()
            if not fields or fields[0] != "cpu" or len(fields) < 5:
                raise ValueError("missing aggregate CPU counters")
            # Guest and guest_nice are already in user and nice.
            ticks = [int(field) for field in fields[1:9]]
            if min(ticks) < 0:
                raise ValueError("negative CPU counter")
            current = (sum(ticks), sum(ticks[3:5]))
        except (OSError, ValueError) as exc:
            return _Reading(source=path, error=str(exc))

        previous = self._previous
        if update_baseline:
            self._previous = current
        if previous is None:
            return _Reading(source=path, error="Waiting for a second CPU counter sample")
        total, idle = (current[i] - previous[i] for i in range(2))
        if total <= 0 or not 0 <= idle <= total:
            return _Reading(source=path, error="No valid CPU counter delta")
        return _Reading(100 * (total - idle) / total, path)

    def _frequency(self) -> _Reading:
        offline = set()
        values = []
        for name in self._sysfs._entries(_CPUFREQ).value or ():
            if not _CPU.fullmatch(name):
                continue
            core = _CPUFREQ / name
            if self._sysfs.read_text(core / "online").value == "0":
                offline.add(int(name[3:]))
                continue
            for attr in ("scaling_cur_freq", "cpuinfo_cur_freq"):
                result = self._sysfs.read_number(core / "cpufreq" / attr, 1e-3)
                if result.value is not None and result.value > 0:
                    values.append(result.value)
                    break
        if values:
            return _Reading(sum(values) / len(values), self._sysfs.root / _CPUFREQ)

        path = self._proc_root / "cpuinfo"
        try:
            with path.open(encoding="utf-8", errors="replace") as cpuinfo:
                core_id = None
                for line in cpuinfo:
                    key, _, value = line.partition(":")
                    if not key.strip():
                        core_id = None
                    elif key.strip() == "processor":
                        core_id = int(value) if value.strip().isdigit() else None
                    elif key.strip() == "cpu MHz" and core_id not in offline:
                        try:
                            mhz = float(value)
                        except ValueError:
                            continue
                        if math.isfinite(mhz) and mhz > 0:
                            values.append(mhz)
        except OSError as exc:
            return _Reading(source=path, error="No readable cpufreq data; {}".format(exc))
        if values:
            return _Reading(sum(values) / len(values), path)
        return _Reading(source=path, error="No readable online CPU frequencies")

    def _temperature(self, chips: Sequence[HwmonChip], package: bool) -> _Reading:
        amd_labels = ("tctl", "tdie") if package else ("tdie", "tctl")

        def rank(chip_name: str, label: str) -> Optional[int]:
            if chip_name in ("k10temp", "zenpower") and label in amd_labels:
                return amd_labels.index(label)
            if chip_name == "coretemp":
                if re.fullmatch(r"package(?: id [0-9]+)?|physical id [0-9]+", label):
                    return 0
                if not package and re.fullmatch(r"core [0-9]+", label):
                    return 1
            if chip_name == "acpitz" and not package and label in ("cpu", "cpu temperature"):
                return 0
            return None

        sensor = "CPU package" if package else "CPU"
        last = _Reading(error="No confirmed {} temperature channels".format(sensor))
        for chip in chips:
            candidates = []
            for channel in chip.channels:
                if channel.kind != "temp":
                    continue
                priority = rank(chip.name, (channel.label or "").strip().casefold())
                if priority is not None:
                    candidates.append((priority, channel))
            for _, channel in sorted(candidates, key=lambda candidate: candidate[0]):
                result = self._sysfs.read_number(channel.input_path, 1e-3)
                last = _Reading(result.value, self._sysfs.root / channel.input_path, result.error)
                if last.value is not None:
                    return last
        return last

    def _power(self, chips: Sequence[HwmonChip]) -> _Reading:
        paths = []
        for chip in chips:
            if chip.name == "acpitz":
                continue
            for attr in self._sysfs._entries(chip.canonical_path).value or ():
                match = _POWER.fullmatch(attr)
                if match:
                    channel, kind = match.groups()
                    label = self._sysfs.read_text(
                        chip.canonical_path / ("power" + channel + "_label")
                    ).value or ""
                    priority = (kind != "average", "package" not in label.casefold())
                    paths.append((priority, chip.canonical_path / attr))
        last = _Reading(error="No CPU hwmon power channels")
        for _, path in sorted(paths, key=lambda entry: entry[0]):
            result = self._sysfs.read_number(path, 1e-6)
            if result.value is not None and result.value >= 0:
                return _Reading(result.value, self._sysfs.root / path)
            last = _Reading(source=self._sysfs.root / path,
                            error=result.error or "CPU power cannot be negative")
        return last


    def _package_power(self, update_baseline: bool) -> Optional[_Reading]:
        bases = (_POWERCAP,) + tuple(_POWERCAP / driver for driver in _RAPL_DRIVERS)
        for base in bases:
            for name in self._sysfs._entries(base).value or ():
                if not _RAPL_ZONE.fullmatch(name):
                    continue
                zone = self._sysfs._target(base / name).value
                if zone is None:
                    continue
                label = self._sysfs.read_text(zone / "name").value or ""
                if re.fullmatch(r"package-[0-9]+", label):
                    return self._energy_delta(zone, update_baseline)
        if update_baseline:
            self._previous_energy = None
        return None

    def _energy_delta(self, zone: Path, update_baseline: bool) -> _Reading:
        energy_path = zone / "energy_uj"
        source = self._sysfs.root / energy_path
        now = self._elapsed_clock()
        energy = self._sysfs.read_number(energy_path)
        previous = self._previous_energy
        if energy.value is None or energy.value < 0:
            if update_baseline:
                self._previous_energy = None
            return _Reading(source=source, error=energy.error or "Negative CPU package energy")

        if previous is None or previous[0] != zone:
            if update_baseline:
                self._previous_energy = (zone, now, energy.value)
            return _Reading(source=source, error="Waiting for a second CPU package energy sample")

        _, last_at, last_energy = previous
        seconds = now - last_at
        if seconds <= 0:
            return _Reading(source=source, error="No elapsed time between CPU energy samples")
        if update_baseline:
            self._previous_energy = (zone, now, energy.value)

        delta = energy.value - last_energy
        if delta < 0:
            maximum = self._sysfs.read_number(zone / "max_energy_range_uj").value
            if maximum is None or not 0 <= energy.value < last_energy <= maximum:
                return _Reading(source=source, error="CPU energy counter decreased without a valid range")
            delta += maximum
        return _Reading(delta / seconds * 1e-6, source)
