# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect provider snapshots and map selected readings to the screen protocol."""

import math
import time
from dataclasses import replace
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple, Union

import ryuo_proto as proto

from ..models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot
from .base import TelemetryProvider

_REPROBE_SECONDS = 60.0
_Number = Union[int, float]


def _number(measurement: Optional[Measurement]) -> _Number:
    if measurement is not None and measurement.available:
        value = measurement.value
        if isinstance(value, int) or (isinstance(value, float) and math.isfinite(value)):
            return value
    return 0


class TelemetryCollector:
    def __init__(
        self, providers: Sequence[TelemetryProvider], preferred_gpu_provider: Optional[str] = None,
        *, clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._providers = tuple(providers)
        self._preferred_gpu_provider = preferred_gpu_provider
        self._selectors: Dict[str, SensorRef] = {}
        self._manual_gpu_supported = False
        self._manual_board_supported = False
        self._clock = clock
        self._last_probe: Optional[float] = None
        self._descriptors: Dict[str, Tuple[SensorDescriptor, ...]] = {}
        self._probe_errors: Dict[str, str] = {}
        self._samples: Dict[str, TelemetrySnapshot] = {}

    def set_selectors(self, selectors: Mapping[str, SensorRef]) -> None:
        """Apply persisted overrides before sampling, on the collector owner thread."""
        if selectors == self._selectors:
            return
        self._selectors = dict(selectors)
        gpu = self._selectors.get("gpu")
        board = self._selectors.get("motherboard")
        self._manual_gpu_supported = False
        self._manual_board_supported = False
        for provider in self._providers:
            set_gpu = getattr(provider, "set_device_override", None)
            if callable(set_gpu):
                matches = gpu is not None and gpu.provider == provider.provider_id
                set_gpu(gpu.device if matches else None)
                self._manual_gpu_supported |= matches
            set_board = getattr(provider, "set_motherboard_override", None)
            if callable(set_board):
                matches = board is not None and board.provider == provider.provider_id
                set_board(board if matches else None)
                self._manual_board_supported |= matches
        self.invalidate()

    def invalidate(self) -> None:
        """Schedule a fresh probe at the next sample or catalog request."""
        self._last_probe = None

    def probe(self) -> Sequence[SensorDescriptor]:
        """Refresh the catalog for every provider independently."""
        self._probe_errors = {}
        for provider in self._providers:
            try:
                self._descriptors[provider.provider_id] = tuple(provider.probe())
            except Exception as exc:
                self._probe_errors[provider.provider_id] = "Probe: {}".format(exc)
        self._last_probe = self._clock()
        self._samples.clear()
        return self._catalog()

    def catalog(self) -> Sequence[SensorDescriptor]:
        self._ensure_probed()
        return self._catalog()

    def _ensure_probed(self) -> None:
        if self._last_probe is None or self._clock() - self._last_probe >= _REPROBE_SECONDS:
            self.probe()

    def _catalog(self) -> Tuple[SensorDescriptor, ...]:
        entries = []
        for provider_id, descriptors in self._descriptors.items():
            snapshot = self._samples.get(provider_id)
            for descriptor in descriptors:
                measurement = snapshot.measurements.get(descriptor.measurement_id) if snapshot else None
                if measurement is not None and measurement.ref == descriptor.ref:
                    descriptor = replace(
                        descriptor, available=measurement.available, error=measurement.error,
                    )
                elif descriptor.metadata.get("selected") is not False:
                    error = self._probe_errors.get(provider_id)
                    if snapshot is not None:
                        error = snapshot.errors.get(provider_id) or error
                        if error is None:
                            error = "Sensor did not report a sample"
                    if error is not None:
                        descriptor = replace(descriptor, available=False, error=error)
                entries.append(descriptor)
        return tuple(entries)

    def sample(self) -> TelemetrySnapshot:
        self._ensure_probed()
        sampled_at = time.time()
        measurements = {}
        errors = dict(self._probe_errors)
        gpu_by_provider = {}
        for provider in self._providers:
            provider_id = provider.provider_id
            try:
                snapshot = provider.sample()
            except Exception as exc:
                snapshot = TelemetrySnapshot({}, sampled_at, {provider_id: "Sample: {}".format(exc)})
            snapshot = self._fill_disappeared(provider_id, snapshot)
            self._samples[provider_id] = snapshot
            errors.update(snapshot.errors)
            gpu = {}
            for key, measurement in snapshot.measurements.items():
                if key.startswith("gpu."):
                    gpu[key] = measurement
                else:
                    measurements[key] = measurement
            if gpu:
                gpu_by_provider[provider_id] = gpu

        gpu = self._selectors.get("gpu")
        board = self._selectors.get("motherboard")
        if board is not None and (
            not self._manual_board_supported
            or not measurements.get("motherboard.temperature")
            or measurements["motherboard.temperature"].ref != board
        ):
            key = "motherboard.temperature"
            error = "Configured motherboard sensor is unavailable: {}".format(board.stable_id)
            measurements[key] = Measurement(board, key, None, "°C", sampled_at,
                                            available=False, error=error)

        preferred = self._preferred_gpu_provider
        if gpu is not None:
            if self._manual_gpu_supported and gpu.provider in gpu_by_provider:
                measurements.update(gpu_by_provider[gpu.provider])
            else:
                errors.setdefault(gpu.provider, "Configured GPU {} is unavailable".format(gpu.device))
        elif preferred is not None:
            if preferred in gpu_by_provider:
                measurements.update(gpu_by_provider[preferred])
            else:
                errors.setdefault(preferred, "Configured GPU provider did not report a device")
        elif gpu_by_provider:
            # Keep the chosen GPU together, including its missing readings.
            gpu = next(
                (metrics for metrics in gpu_by_provider.values()
                 if any(m.available and m.value is not None for m in metrics.values())),
                next(iter(gpu_by_provider.values())),
            )
            measurements.update(gpu)
        return TelemetrySnapshot(measurements, sampled_at, errors)

    def _fill_disappeared(
        self, provider_id: str, snapshot: TelemetrySnapshot,
    ) -> TelemetrySnapshot:
        # Keep discovered non-GPU sensors visible until reprobe. GPU absence
        # is represented by the provider error and must not win auto selection.
        missing = {}
        for descriptor in self._descriptors.get(provider_id, ()):
            key = descriptor.measurement_id
            if (key.startswith("gpu.") or key in snapshot.measurements
                    or descriptor.metadata.get("selected") is False):
                continue
            error = snapshot.errors.get(provider_id) or "Sensor did not report a sample"
            missing[key] = Measurement(
                descriptor.ref, key, None, descriptor.unit, snapshot.sampled_at,
                available=False, error=error,
            )
        return replace(snapshot, measurements={**snapshot.measurements, **missing}) if missing else snapshot

    def to_pc_info(
        self, snapshot: TelemetrySnapshot, *,
        extra_readouts: Optional[Mapping[str, _Number]] = None,
        fan_aliases: Optional[Mapping[Tuple[str, SensorRef], str]] = None,
    ) -> dict:
        """Build the legacy payload; unavailable values become zero here.

        Host memory and disk retain the protocol defaults. The direct CLI
        supplies its existing psutil readings separately.
        """
        measurements = snapshot.measurements

        def value(key: str) -> _Number:
            return _number(measurements.get(key))

        labels: Dict[Tuple[str, SensorRef], str] = {
            (d.measurement_id, d.ref): d.label
            for descriptors in self._descriptors.values()
            for d in descriptors
            if d.unit == "RPM"
        }
        fans = [
            {
                "onBoard": True,
                "name": (fan_aliases or {}).get(
                    (key, reading.ref),
                    labels.get((key, reading.ref), reading.ref.channel),
                ),
                "value": int(_number(reading)),
            }
            for key, reading in measurements.items()
            if key.startswith("fan.") and key.endswith(".rpm") and reading.unit == "RPM"
        ]
        fans.extend({"onBoard": True, "name": label, "value": int(reading)}
                    for label, reading in (extra_readouts or {}).items())
        return proto.pc_info(
            cpu={
                "load": int(value("cpu.load")),
                "temperature": round(value("cpu.temperature")),
                "temperaturePackage": round(value("cpu.temperature.package")),
                "speedAverage": int(value("cpu.frequency")),
                "power": int(value("cpu.power")),
                "voltage": value("cpu.voltage"),
                "usage": int(value("cpu.usage" if "cpu.usage" in measurements else "cpu.load")),
            },
            gpu={
                "hasDedicated": any(key.startswith("gpu.") for key in measurements),
                "load": int(value("gpu.load")),
                "temperature": int(value("gpu.temperature")),
                "fan": int(value("gpu.fan")),
                "speed": int(value("gpu.clock.core")),
                "power": int(value("gpu.power")),
                "voltage": value("gpu.voltage"),
            },
            motherboard={
                "temperature": round(value("motherboard.temperature")),
                "chipsetTemperature": round(value("motherboard.temperature.chipset")),
            },
            fans=fans,
            timestamp_ms=int(snapshot.sampled_at * 1000),
        )
