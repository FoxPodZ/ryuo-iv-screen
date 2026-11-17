# SPDX-License-Identifier: GPL-3.0-or-later
"""Motherboard temperatures and fan readings with physical hwmon selectors."""

import hashlib
import time
from dataclasses import replace
from typing import Callable, List, Optional, Sequence, Tuple

from ..models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot
from .sysfs import HwmonChannel, ReadResult, Sysfs, enumerate_hwmon

_BOARD_METRIC = "motherboard.temperature"
_BOARD_LABELS = ("motherboard", "board", "systin", "system", "system 1")
_NON_BOARD_CHIPS = {"amdgpu", "nouveau", "nvidia", "k10temp", "zenpower", "coretemp", "acpitz"}


class HwmonProvider:
    provider_id = "hwmon"

    def __init__(
        self, sysfs: Sysfs, motherboard_ref: Optional[SensorRef] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._sysfs = sysfs
        self._startup_motherboard_ref = motherboard_ref
        self._motherboard_ref = motherboard_ref
        self._clock = clock

    def set_motherboard_override(self, ref: Optional[SensorRef]) -> None:
        self._motherboard_ref = self._startup_motherboard_ref if ref is None else ref

    def probe(self) -> Sequence[SensorDescriptor]:
        fans, temperatures = self._channels()
        board, _ = self._board(temperatures)
        descriptors = [self._fan(channel, name)[0] for channel, name in fans]
        for channel, _ in temperatures:
            selected = channel.ref == board.ref
            descriptor = board if selected else self._temperature(channel, self._read(channel, 1e-3))
            descriptors.append(replace(descriptor, metadata={"selected": selected}))
        if not any(channel.ref == board.ref for channel, _ in temperatures):
            descriptors.append(replace(board, metadata={"selected": True}))
        return descriptors

    def sample(self) -> TelemetrySnapshot:
        sampled_at = self._clock()
        fans, temperatures = self._channels()
        readings = [self._board(temperatures)]
        readings.extend(self._fan(channel, name) for channel, name in fans)
        return TelemetrySnapshot({
            descriptor.measurement_id: Measurement(
                descriptor.ref, descriptor.measurement_id, value, descriptor.unit, sampled_at,
                available=descriptor.available, error=descriptor.error,
            )
            for descriptor, value in readings
        }, sampled_at)

    def _channels(
        self,
    ) -> Tuple[List[Tuple[HwmonChannel, str]], List[Tuple[HwmonChannel, str]]]:
        fans, temperatures = [], []
        for chip in enumerate_hwmon(self._sysfs):
            for channel in chip.channels:
                if channel.kind == "fan":
                    fans.append((channel, chip.name))
                elif channel.kind == "temp":
                    temperatures.append((channel, chip.name))
        # Class indexes can change without changing the order of physical sensors.
        return (sorted(fans, key=lambda entry: entry[0].ref.stable_id),
                sorted(temperatures, key=lambda entry: entry[0].ref.stable_id))

    def _read(self, channel: HwmonChannel, scale: float = 1.0) -> ReadResult[float]:
        return self._sysfs.read_number(channel.input_path, scale)

    def _fan(
        self, channel: HwmonChannel, chip_name: str,
    ) -> Tuple[SensorDescriptor, Optional[float]]:
        token = hashlib.sha256(channel.ref.stable_id.encode("ascii")).hexdigest()[:20]
        reading = self._read(channel)
        descriptor = self._descriptor(
            channel, "fan.{}.rpm".format(token), chip_name, "RPM", reading,
        )
        return descriptor, reading.value

    def _board(
        self, temperatures: Sequence[Tuple[HwmonChannel, str]],
    ) -> Tuple[SensorDescriptor, Optional[float]]:
        manual = self._motherboard_ref
        if manual is not None:
            candidates = [channel for channel, _ in temperatures if channel.ref == manual]
        else:
            ranked = []
            for channel, name in temperatures:
                label = (channel.label or "").strip().casefold()
                if name not in _NON_BOARD_CHIPS and label in _BOARD_LABELS:
                    ranked.append((_BOARD_LABELS.index(label), not name.startswith("nct67"), channel))
            candidates = [entry[2] for entry in sorted(ranked, key=lambda entry: entry[:2])]

        failed = None
        for channel in candidates:
            reading = self._read(channel, 1e-3)
            descriptor = self._temperature(channel, reading)
            if reading.value is not None:
                return descriptor, reading.value
            if failed is None:
                failed = descriptor

        if failed is not None:
            return failed, None
        if manual is not None:
            ref = manual
            error = "Configured motherboard sensor is unavailable: {}".format(ref.stable_id)
        else:
            ref = SensorRef(self.provider_id, "host", _BOARD_METRIC)
            error = "No hwmon temperature with a recognized motherboard label"
        return SensorDescriptor(
            ref, _BOARD_METRIC, "Motherboard temperature", "°C", available=False, error=error,
        ), None

    def _temperature(self, channel: HwmonChannel, reading: ReadResult[float]) -> SensorDescriptor:
        return self._descriptor(channel, _BOARD_METRIC, "Motherboard temperature", "°C", reading)

    def _descriptor(
        self, channel: HwmonChannel, key: str, fallback_label: str, unit: str,
        reading: ReadResult[float],
    ) -> SensorDescriptor:
        return SensorDescriptor(
            channel.ref, key, channel.label or fallback_label, unit,
            available=reading.value is not None,
            source=str(self._sysfs.root / channel.input_path), error=reading.error,
        )
