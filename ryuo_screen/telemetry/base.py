# SPDX-License-Identifier: GPL-3.0-or-later
"""Interface for telemetry providers."""

from typing import Protocol, Sequence

from ..models import SensorDescriptor, TelemetrySnapshot


class TelemetryProvider(Protocol):
    provider_id: str

    def probe(self) -> Sequence[SensorDescriptor]:
        ...

    def sample(self) -> TelemetrySnapshot:
        ...
