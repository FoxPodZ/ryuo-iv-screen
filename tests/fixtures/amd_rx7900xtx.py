# SPDX-License-Identifier: GPL-3.0-or-later
"""A fake RX 7900 XTX PCI device with amdgpu telemetry."""

from pathlib import Path
from typing import Tuple

from .sysfs_builder import SysfsBuilder

RX_7900_XTX_BDF = "0000:03:00.0"


def rx7900xtx(
    fake: SysfsBuilder, index: int = 2, card: str = "card1",
    hwmon_under_drm: bool = False,
) -> Tuple[Path, Path]:
    gpu = fake.pci(bdf=RX_7900_XTX_BDF, device="0x744c", card=card)
    for name, value in (
        ("product_name", "AMD Radeon RX 7900 XTX"),
        ("gpu_busy_percent", "42"),
        ("mem_info_vram_used", "1610612736"),
        ("mem_info_vram_total", "25769803776"),
    ):
        (gpu / name).write_text(value + "\n", encoding="ascii")

    # The normal amdgpu layout uses the PCI device. Also model a class-tree
    # target to exercise renumbering when the hwmon device link includes DRM.
    parent = gpu / "drm" / card if hwmon_under_drm else gpu
    chip = fake.hwmon(parent, index, "amdgpu", {
        "temp1": (45400, "edge"),
        "temp2": (62100, "junction"),
        "temp3": (54300, "mem"),
        "freq1": (800000000, None),
        "freq2": (700000000, "unrelated"),
        "freq3": (2365000000, "sclk"),
        "freq5": (1250000000, "mclk"),
        "power1": (113000000, None),
        "fan1": (1100, "GPU fan"),
    })
    (chip / "power1_average").write_text("108750000\n", encoding="ascii")
    return gpu, chip
