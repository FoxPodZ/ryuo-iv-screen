# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared models for telemetry and screen commands."""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Union
from urllib.parse import quote

Scalar = Union[int, float, str]


@dataclass(frozen=True)
class SensorRef:
    provider: str
    device: str
    channel: str

    def __post_init__(self) -> None:
        if any("\x00" in part for part in (self.provider, self.device, self.channel)):
            raise ValueError("sensor references cannot contain NUL")

    def to_dict(self) -> Dict[str, str]:
        return {
            "provider": self.provider,
            "device": self.device,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SensorRef":
        return cls(
            provider=data["provider"],
            device=data["device"],
            channel=data["channel"],
        )

    @property
    def stable_id(self) -> str:
        """Join escaped components so a slash in an identity stays unambiguous."""
        parts = (self.provider, self.device, self.channel)
        return "/".join(quote(part, safe="") for part in parts)


@dataclass(frozen=True)
class SensorDescriptor:
    ref: SensorRef
    measurement_id: str
    label: str
    unit: str
    available: bool = True
    source: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass(frozen=True)
class Measurement:
    ref: SensorRef
    measurement_id: str
    value: Optional[Scalar]
    unit: str
    sampled_at: float
    available: bool = True
    error: Optional[str] = None


@dataclass(frozen=True)
class TelemetrySnapshot:
    """One sample of measurements keyed by logical measurement ID."""

    measurements: Mapping[str, Measurement]
    sampled_at: float
    errors: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    method: str
    resource: str
    payload: Optional[Mapping[str, Any]] = None
    priority: int = 100
    coalesce_key: Optional[str] = None


@dataclass(frozen=True)
class CommandResult:
    saved: bool = False
    queued: bool = False
    applied: bool = False
    acked: bool = False
    error: Optional[str] = None
