# SPDX-License-Identifier: GPL-3.0-or-later
"""Read native amdgpu telemetry by PCI address."""

import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ..models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot
from .sysfs import HwmonChip, PciDevice, ReadResult, Sysfs, enumerate_hwmon, enumerate_pci

_DISPLAY_CLASS = re.compile(r"0x03[0-9a-f]{4}", re.IGNORECASE)
_ACTIVE_DPM_CLOCK = re.compile(
    r"\s*(?:[0-9]+|S):\s*([0-9]+(?:\.[0-9]+)?)\s*MHz\s*\*\s*", re.IGNORECASE,
)
_UEVENT_DEVICE = re.compile(r"^PCI_ID=1002:([0-9a-f]{4})$", re.IGNORECASE | re.MULTILINE)
_MODALIAS_DEVICE = re.compile(r"pci:v00001002d0000([0-9a-f]{4})sv", re.IGNORECASE)
_TEMP_PRIORITY = {"edge": 0, "junction": 1}
_METRICS = {
    "gpu.temperature": ("GPU temperature", "°C"),
    "gpu.load": ("GPU load", "%"),
    "gpu.clock.core": ("GPU core clock", "MHz"),
    "gpu.clock.memory": ("GPU memory clock", "MHz"),
    "gpu.vram.used": ("GPU VRAM used", "B"),
    "gpu.vram.total": ("GPU VRAM total", "B"),
    "gpu.power": ("GPU power", "W"),
    "gpu.fan": ("GPU fan", "RPM"),
}


@dataclass(frozen=True)
class _Input:
    path: Path
    scale: float = 1.0
    label: Optional[str] = None
    dpm: bool = False

    @property
    def normalized_label(self) -> str:
        return (self.label or "").casefold()


@dataclass(frozen=True)
class _Reading:
    value: Optional[Union[int, float]] = None
    source: Optional[Path] = None
    error: Optional[str] = None
    source_label: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.value is not None


class AmdGpuProvider:
    provider_id = "amd"

    def __init__(self, sysfs: Sysfs, selected_bdf: Optional[str] = None) -> None:
        self._sysfs = sysfs
        self._startup_bdf = selected_bdf.strip().lower() if selected_bdf is not None else None
        self._selected_bdf = self._startup_bdf

    def set_device_override(self, device: Optional[str]) -> None:
        self._selected_bdf = self._startup_bdf if device is None else device

    def probe(self) -> Sequence[SensorDescriptor]:
        """Catalog every AMD GPU even when the configured PCI address is absent."""
        devices, selected, totals = self._discover()
        chips = self._hwmon_by_device() if devices else {}
        descriptors = []
        for device in devices:
            metadata = self._metadata(device, device == selected)
            readings = self._readings(device, chips.get(device.device_id, ()), totals.get(device.bdf))
            for measurement_id, (label, unit) in _METRICS.items():
                reading = readings[measurement_id]
                entry_metadata = dict(metadata)
                if reading.source_label:
                    entry_metadata["source_label"] = reading.source_label
                descriptors.append(SensorDescriptor(
                    ref=self._ref(device, measurement_id),
                    measurement_id=measurement_id,
                    label=label,
                    unit=unit,
                    available=reading.available,
                    source=str(reading.source) if reading.source is not None else None,
                    metadata=entry_metadata,
                    error=reading.error,
                ))
        return descriptors

    def sample(self) -> TelemetrySnapshot:
        """Read the logical measurements for the selected PCI device."""
        sampled_at = time.time()
        _, selected, totals = self._discover()
        if selected is None:
            if self._selected_bdf is not None:
                error = "AMD GPU at PCI address {} is unavailable".format(self._selected_bdf)
            else:
                error = "No AMD display device bound to amdgpu"
            return TelemetrySnapshot({}, sampled_at, {self.provider_id: error})

        chips = self._hwmon_by_device().get(selected.device_id, ())
        readings = self._readings(selected, chips, totals.get(selected.bdf))
        return TelemetrySnapshot({
            measurement_id: Measurement(
                ref=self._ref(selected, measurement_id),
                measurement_id=measurement_id,
                value=reading.value,
                unit=_METRICS[measurement_id][1],
                sampled_at=sampled_at,
                available=reading.available,
                error=reading.error,
            )
            for measurement_id, reading in readings.items()
        }, sampled_at)

    def _ref(self, device: PciDevice, measurement_id: str) -> SensorRef:
        # Fallback files can change without changing the logical sensor.
        return SensorRef(self.provider_id, device.bdf, measurement_id)

    def _discover(self) -> Tuple[List[PciDevice], Optional[PciDevice], Dict[str, _Reading]]:
        devices = [
            device for device in enumerate_pci(self._sysfs)
            if (device.vendor or "").lower() == "0x1002"
            and _DISPLAY_CLASS.fullmatch(device.class_code or "")
            and device.driver == "amdgpu"
        ]
        if self._selected_bdf is not None:
            selected = next((device for device in devices if device.bdf == self._selected_bdf), None)
            return devices, selected, {}

        # Some APUs also report VRAM. Compare the amounts the kernel exposes;
        # an explicit BDF handles systems where this preference is unsuitable.
        totals = {
            device.bdf: self._read_vram(device.path / "mem_info_vram_total")
            for device in devices
        }

        def selection_key(device: PciDevice) -> Tuple[bool, int, str]:
            total = totals[device.bdf].value
            return total is None, -int(total or 0), device.bdf

        return devices, min(devices, key=selection_key, default=None), totals

    def _hwmon_by_device(self) -> Dict[str, List[HwmonChip]]:
        chips = {}
        for chip in enumerate_hwmon(self._sysfs):
            if chip.name == "amdgpu":
                chips.setdefault(chip.device_id, []).append(chip)
        return chips

    def _metadata(self, device: PciDevice, selected: bool) -> Dict[str, Union[bool, str, None]]:
        name = self._sysfs.read_text(device.path / "product_name").value
        if not name:
            name = self._sysfs.read_text(device.path / "label").value
        device_id = device.device
        if not device_id:
            uevent = self._sysfs.read_text(device.path / "uevent").value or ""
            match = _UEVENT_DEVICE.search(uevent)
            if match is None:
                modalias = self._sysfs.read_text(device.path / "modalias").value or ""
                match = _MODALIAS_DEVICE.match(modalias)
            if match is not None:
                device_id = "0x" + match.group(1).lower()
        if not name:
            name = "AMD GPU (PCI device {})".format(device_id) if device_id else "AMD GPU"
        return {
            "bdf": device.bdf,
            "selected": selected,
            "name": name,
            "pci_vendor_id": device.vendor,
            "pci_device_id": device_id,
            "pci_subsystem_vendor_id": self._sysfs.read_text(device.path / "subsystem_vendor").value,
            "pci_subsystem_device_id": self._sysfs.read_text(device.path / "subsystem_device").value,
        }

    def _readings(
        self, device: PciDevice, chips: Sequence[HwmonChip], total: Optional[_Reading],
    ) -> Dict[str, _Reading]:
        path = device.path
        temperatures = sorted(
            _hwmon_inputs(chips, "temp", 1e-3),
            key=lambda source: _TEMP_PRIORITY.get(source.normalized_label, len(_TEMP_PRIORITY)),
        )
        frequencies = list(_hwmon_inputs(chips, "freq", 1e-6))
        power = [
            _Input(chip.canonical_path / attribute, 1e-6)
            for attribute in ("power1_average", "power1_input")
            for chip in chips
        ]
        return {
            "gpu.temperature": self._first_valid(temperatures, "No amdgpu temperature channels"),
            "gpu.load": self._first_valid([_Input(path / "gpu_busy_percent")]),
            "gpu.clock.core": self._read_clock(frequencies, ("sclk", "gfx"), path / "pp_dpm_sclk"),
            "gpu.clock.memory": self._read_clock(frequencies, ("mclk", "mem"), path / "pp_dpm_mclk"),
            "gpu.vram.used": self._read_vram(path / "mem_info_vram_used"),
            "gpu.vram.total": total if total is not None else self._read_vram(path / "mem_info_vram_total"),
            "gpu.power": self._first_valid(power, "No amdgpu hwmon power channels"),
            "gpu.fan": self._first_valid(_hwmon_inputs(chips, "fan"), "No amdgpu fan channels"),
        }

    def _first_valid(
        self, sources: Iterable[_Input], missing: str = "No matching sysfs attributes",
    ) -> _Reading:
        errors = []
        for source in sources:
            result = (
                self._read_dpm_clock(source.path)
                if source.dpm else self._sysfs.read_number(source.path, source.scale)
            )
            if result.value is not None:
                return _Reading(result.value, source.path, source_label=source.label)
            errors.append("{}: {}".format(source.path, result.error))
        return _Reading(error="; ".join(errors) if errors else missing)

    def _read_clock(
        self, frequencies: Sequence[_Input], labels: Tuple[str, ...], dpm_path: Path,
    ) -> _Reading:
        sources = [
            source for label in labels for source in frequencies
            if source.normalized_label == label
        ]
        sources.append(_Input(dpm_path, dpm=True))
        return self._first_valid(sources)

    def _read_dpm_clock(self, path: Path) -> ReadResult[float]:
        result = self._sysfs.read_text(path)
        if result.value is None:
            return ReadResult(error=result.error)
        active = []
        for line in result.value.splitlines():
            match = _ACTIVE_DPM_CLOCK.fullmatch(line)
            if match is not None:
                active.append(match.group(1))
        if len(active) == 1:
            value = float(active[0])
            if math.isfinite(value):
                return ReadResult(value)
        return ReadResult(error="No unambiguous active MHz clock")

    def _read_vram(self, path: Path) -> _Reading:
        result = self._sysfs.read_text(path)
        if result.value is not None:
            try:
                value = int(result.value)
                if value >= 0:
                    return _Reading(value, path)
            except ValueError:
                pass
            return _Reading(error="{}: expected a nonnegative byte count".format(path))
        return _Reading(error=result.error)


def _hwmon_inputs(
    chips: Sequence[HwmonChip], kind: str, scale: float = 1.0,
) -> Iterable[_Input]:
    for chip in chips:
        for channel in chip.channels:
            if channel.kind == kind:
                yield _Input(channel.input_path, scale, channel.label)
