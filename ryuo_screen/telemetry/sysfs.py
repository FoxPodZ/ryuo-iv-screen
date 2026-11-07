# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only discovery of Linux PCI devices and hwmon sensors."""

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, List, Mapping, Optional, Sequence, Tuple, TypeVar, Union

from ..models import SensorRef

T = TypeVar("T")
RelativePath = Union[str, Path]

_PCI_BDF = re.compile(r"[0-9a-f]{4,}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]")
_HWMON = re.compile(r"hwmon[0-9]+")
_CARD = re.compile(r"card[0-9]+")
_INPUT = re.compile(r"([a-z]+)([0-9]+)_input")
_PATH_ERRORS = (OSError, RuntimeError, ValueError)


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    value: Optional[T] = None
    error: Optional[str] = None


def _reason(exc: Exception) -> str:
    return "{}: {}".format(type(exc).__name__, exc)


class Sysfs:
    def __init__(self, root: Path = Path("/sys")) -> None:
        self.root = Path(root).resolve()

    def _resolve(self, relative: RelativePath) -> Path:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("expected a path relative to the sysfs root: {}".format(path))
        resolved = (self.root / path).resolve(strict=True)
        try:
            return resolved.relative_to(self.root)
        except ValueError:
            raise ValueError("path escapes the sysfs root: {}".format(path)) from None

    def _open(self, relative: RelativePath, flags: int) -> int:
        # After resolving sysfs aliases, walk the canonical path by directory
        # descriptors so a symlink inserted during a read cannot redirect it.
        parts = self._resolve(relative).parts
        if not parts:
            return os.open(self.root, flags | os.O_NOFOLLOW)
        dir_flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(self.root, dir_flags)
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, dir_flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=fd)
        finally:
            os.close(fd)

    def _target(self, relative: RelativePath) -> ReadResult[Path]:
        try:
            return ReadResult(self._resolve(relative))
        except _PATH_ERRORS as exc:
            return ReadResult(error=_reason(exc))

    def _entries(self, relative: RelativePath) -> ReadResult[List[str]]:
        try:
            fd = self._open(relative, os.O_RDONLY | os.O_DIRECTORY)
            try:
                return ReadResult(sorted(os.listdir(fd)))
            finally:
                os.close(fd)
        except _PATH_ERRORS as exc:
            return ReadResult(error=_reason(exc))

    def read_text(self, relative: RelativePath) -> ReadResult[str]:
        try:
            with os.fdopen(self._open(relative, os.O_RDONLY), encoding="utf-8") as file:
                return ReadResult(file.read().strip())
        except _PATH_ERRORS as exc:
            return ReadResult(error=_reason(exc))

    def read_number(self, relative: RelativePath, scale: float = 1.0) -> ReadResult[float]:
        """Parse a sysfs number and multiply it by the supplied unit scale."""
        text = self.read_text(relative)
        if text.value is None:
            return ReadResult(error=text.error)
        try:
            value = float(text.value) * scale
            if not math.isfinite(value):
                raise ValueError("number is not finite")
            return ReadResult(value)
        except ValueError as exc:
            return ReadResult(error=_reason(exc))


@dataclass(frozen=True)
class PciDevice:
    bdf: str
    path: Path
    vendor: Optional[str]
    device: Optional[str]
    class_code: Optional[str]
    driver: Optional[str]
    errors: Mapping[str, str] = field(default_factory=dict)

    @property
    def device_id(self) -> str:
        return "pci/" + self.bdf


@dataclass(frozen=True)
class HwmonChannel:
    ref: SensorRef
    input_path: Path
    label: Optional[str]
    kind: str


@dataclass(frozen=True)
class HwmonChip:
    name: str
    path: Path
    device_id: str
    channels: Tuple[HwmonChannel, ...]


def enumerate_pci(sysfs: Sysfs) -> List[PciDevice]:
    devices = []
    base = Path("bus/pci/devices")
    for bdf in sysfs._entries(base).value or ():
        path = base / bdf
        if not _PCI_BDF.fullmatch(bdf) or sysfs._target(path).value is None:
            continue
        attrs = {name: sysfs.read_text(path / name) for name in ("vendor", "device", "class")}
        target = sysfs._target(path / "driver")
        errors = {name: result.error for name, result in attrs.items() if result.error is not None}
        if target.error is not None:
            errors["driver"] = target.error
        devices.append(PciDevice(
            bdf=bdf,
            path=path,
            vendor=attrs["vendor"].value,
            device=attrs["device"].value,
            class_code=attrs["class"].value,
            driver=target.value.name if target.value is not None else None,
            errors=errors,
        ))
    return devices


def _hwmon_device_id(target: Path) -> Optional[str]:
    # The device link ordinarily points to the physical device itself. Some
    # layouts point into its class tree, where the index is only a runtime alias.
    parts = [
        part for index, part in enumerate(target.parts)
        if not (_HWMON.fullmatch(part) or _CARD.fullmatch(part))
        and not (
            index + 1 < len(target.parts)
            and (
                (part == "hwmon" and _HWMON.fullmatch(target.parts[index + 1]))
                or (part == "drm" and _CARD.fullmatch(target.parts[index + 1]))
            )
        )
    ]
    for index in range(len(parts) - 1, -1, -1):
        if _PCI_BDF.fullmatch(parts[index]):
            return "/".join(["pci"] + parts[index:])
    if parts and parts[0] == "devices":
        parts = parts[1:]
    return "/".join(parts) if parts else None


def _hwmon_channels(sysfs: Sysfs, path: Path, device_id: str) -> Tuple[HwmonChannel, ...]:
    channels = []
    for entry in sysfs._entries(path).value or ():
        match = _INPUT.fullmatch(entry)
        if match:
            kind, index = match.groups()
            channels.append((kind, int(index), kind + index, path / entry))
    return tuple(
        HwmonChannel(
            ref=SensorRef("hwmon", device_id, channel),
            input_path=input_path,
            label=sysfs.read_text(path / (channel + "_label")).value,
            kind=kind,
        )
        for kind, _, channel, input_path in sorted(channels)
    )


def enumerate_hwmon(sysfs: Sysfs) -> List[HwmonChip]:
    chips = []
    base = Path("class/hwmon")
    for entry in sysfs._entries(base).value or ():
        if not _HWMON.fullmatch(entry):
            continue
        path = base / entry
        name = sysfs.read_text(path / "name").value
        target = sysfs._target(path / "device").value
        if not name or target is None:
            continue
        device_id = _hwmon_device_id(target)
        if device_id is not None:
            chips.append(HwmonChip(name, path, device_id, _hwmon_channels(sysfs, path, device_id)))
    return chips


def find_channel(
    chip: HwmonChip, kind: str, labels: Sequence[str] = (),
) -> Optional[HwmonChannel]:
    """Find the first channel of a kind, preferring labels in the given order."""
    candidates = [channel for channel in chip.channels if channel.kind == kind]
    if not labels:
        return next(iter(candidates), None)
    for label in labels:
        for channel in candidates:
            if channel.label is not None and channel.label.casefold() == label.casefold():
                return channel
    return None
