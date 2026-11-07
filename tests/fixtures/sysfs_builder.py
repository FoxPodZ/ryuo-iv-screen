# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a small on-disk sysfs tree with the same links as Linux exposes."""

import os
from pathlib import Path
from typing import Mapping, Optional, Tuple


class SysfsBuilder:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir()

    @staticmethod
    def link(path: Path, target: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(os.path.relpath(target, path.parent))

    def pci(
        self,
        bdf: str = "0000:03:00.0",
        vendor: str = "0x1002",
        device: str = "0x73bf",
        class_code: str = "0x030000",
        driver: str = "amdgpu",
        card: Optional[str] = None,
    ) -> Path:
        target = self.root / "devices/pci0000:00/0000:00:01.0" / bdf
        target.mkdir(parents=True)
        for name, value in (("vendor", vendor), ("device", device), ("class", class_code)):
            (target / name).write_text(value + "\n", encoding="ascii")
        driver_path = self.root / "bus/pci/drivers" / driver
        driver_path.mkdir(parents=True, exist_ok=True)
        self.link(target / "driver", driver_path)
        self.link(self.root / "bus/pci/devices" / bdf, target)
        if card is not None:
            card_path = target / "drm" / card
            card_path.mkdir(parents=True)
            self.link(card_path / "device", target)
            self.link(self.root / "class/drm" / card, card_path)
        return target

    def hwmon(
        self,
        device: Path,
        index: int,
        name: str,
        channels: Mapping[str, Tuple[int, Optional[str]]],
    ) -> Path:
        hwmon = "hwmon{}".format(index)
        target = device / "hwmon" / hwmon
        target.mkdir(parents=True)
        self.link(target / "device", device)
        self.link(self.root / "class/hwmon" / hwmon, target)
        (target / "name").write_text(name + "\n", encoding="ascii")
        for channel, (value, label) in channels.items():
            (target / (channel + "_input")).write_text(str(value) + "\n", encoding="ascii")
            if label is not None:
                (target / (channel + "_label")).write_text(label + "\n", encoding="ascii")
        return target
