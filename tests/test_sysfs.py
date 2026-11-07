# SPDX-License-Identifier: GPL-3.0-or-later
"""Discover Linux telemetry identities without relying on host hardware."""

import os
from pathlib import Path

import pytest

from fixtures.sysfs_builder import SysfsBuilder
from ryuo_screen.models import SensorRef
from ryuo_screen.telemetry.sysfs import (
    Sysfs,
    enumerate_hwmon,
    enumerate_pci,
    find_channel,
)


def test_gpu_identity_survives_hwmon_and_card_renumbering(tmp_path):
    def discover(root, index, card):
        fake = SysfsBuilder(root)
        gpu = fake.pci(card=card)
        fake.hwmon(gpu, index, "amdgpu", {"temp1": (45000, "edge")})
        assert (root / "class/drm" / card / "device").resolve() == gpu
        sysfs = Sysfs(root)
        chip, = enumerate_hwmon(sysfs)
        pci, = enumerate_pci(sysfs)
        channel = find_channel(chip, "temp", ["edge"])
        assert channel is not None
        return chip, pci, channel

    first_chip, first_pci, first_channel = discover(tmp_path / "first", 2, "card1")
    next_chip, next_pci, next_channel = discover(tmp_path / "next", 9, "card0")

    assert first_chip.path == Path("class/hwmon/hwmon2")
    assert next_chip.path == Path("class/hwmon/hwmon9")
    assert first_chip.canonical_path == first_channel.input_path.parent
    assert next_chip.canonical_path == next_channel.input_path.parent
    assert first_chip.name == next_chip.name == "amdgpu"
    assert first_chip.device_id == next_chip.device_id == "pci/0000:03:00.0"
    assert first_pci == next_pci
    assert first_pci.device_id == first_chip.device_id
    assert first_pci.bdf == "0000:03:00.0"
    assert first_pci.path == Path("bus/pci/devices/0000:03:00.0")
    assert (first_pci.vendor, first_pci.device, first_pci.class_code, first_pci.driver) == (
        "0x1002", "0x73bf", "0x030000", "amdgpu",
    )
    assert first_channel.ref == next_channel.ref == SensorRef(
        "hwmon", "pci/0000:03:00.0/amdgpu", "temp1"
    )
    assert not any(
        alias in first_channel.ref.stable_id
        for alias in ("hwmon2", "hwmon9", "card1", "card0")
    )
    pci_path = Path("devices/pci0000:00/0000:00:01.0/0000:03:00.0")
    assert first_channel.input_path == pci_path / "hwmon/hwmon2/temp1_input"
    assert next_channel.input_path == pci_path / "hwmon/hwmon9/temp1_input"


def test_platform_hwmon_uses_canonical_device(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    fake.hwmon(fake.root / "devices/platform/nct6775.656", 2, "nct6775", {"fan2": (600, None)})

    chip, = enumerate_hwmon(Sysfs(fake.root))
    channel = find_channel(chip, "fan", [])

    assert chip.device_id == "platform/nct6775.656"
    assert channel is not None
    assert channel.label is None
    assert channel.ref == SensorRef("hwmon", "platform/nct6775.656/nct6775", "fan2")


def test_read_number_applies_scale_and_preserves_parse_error(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    (fake.root / "temperature").write_text(" -3250\n", encoding="ascii")
    (fake.root / "invalid").write_text("not a number", encoding="ascii")
    sysfs = Sysfs(fake.root)

    valid = sysfs.read_number("temperature", 0.001)
    invalid = sysfs.read_number("invalid", 1)
    missing = sysfs.read_number("missing", 1)

    assert (valid.value, valid.error) == (-3.25, None)
    assert invalid.value is None and "number" in invalid.error
    assert missing.value is None and "FileNotFoundError" in missing.error


def test_read_permission_error_returns_unavailable(tmp_path, monkeypatch):
    fake = SysfsBuilder(tmp_path / "sys")
    (fake.root / "temperature").write_text("42000\n", encoding="ascii")
    original_open = os.open

    def deny_temperature(path, *args, **kwargs):
        if Path(path).name == "temperature":
            raise PermissionError("denied temperature")
        return original_open(path, *args, **kwargs)

    # Inject an open failure so this test also works when pytest runs as root.
    monkeypatch.setattr(os, "open", deny_temperature)
    sysfs = Sysfs(fake.root)

    read = sysfs.read_text("temperature")
    numeric = sysfs.read_number("temperature", 0.001)

    assert read.value is None
    assert "denied temperature" in read.error
    assert numeric.value is None
    assert numeric.error == read.error


def test_disappearing_attribute_does_not_abort_enumeration(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    first = fake.pci()
    fake.pci("0000:05:00.0")
    (first / "vendor").unlink()

    incomplete, remaining = enumerate_pci(Sysfs(fake.root))

    assert incomplete.bdf == "0000:03:00.0"
    assert incomplete.vendor is None
    assert "FileNotFoundError" in incomplete.errors["vendor"]
    assert remaining.bdf == "0000:05:00.0"
    assert remaining.vendor == "0x1002"


def test_symlink_outside_fake_sysfs_is_refused(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    outside = tmp_path / "sys-sibling"
    outside.mkdir()
    (outside / "vendor").write_text("0x1002", encoding="ascii")
    (outside / "name").write_text("amdgpu", encoding="ascii")
    fake.link(fake.root / "escape", outside)
    fake.link(fake.root / "bus/pci/devices/0000:03:00.0", outside)
    fake.link(fake.root / "class/hwmon/hwmon2", outside)
    sysfs = Sysfs(fake.root)

    for path in ("escape/vendor", "../sys-sibling/vendor", outside / "vendor"):
        refused = sysfs.read_text(path)
        assert refused.value is None
        assert refused.error is not None
    assert not enumerate_pci(sysfs)
    assert not enumerate_hwmon(sysfs)


def test_duplicate_labels_stay_distinguishable_by_channel(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    fake.hwmon(
        fake.pci(),
        2,
        "amdgpu",
        {"temp10": (54000, "edge"), "temp2": (45000, "edge"), "temp3": (55000, "junction")},
    )
    chip, = enumerate_hwmon(Sysfs(fake.root))

    duplicates = [channel for channel in chip.channels if channel.label == "edge"]
    assert [channel.ref.channel for channel in duplicates] == ["temp2", "temp10"]
    assert len({channel.ref.stable_id for channel in duplicates}) == 2
    assert find_channel(chip, "temp", ["edge"]) == duplicates[0]
    assert find_channel(chip, "temp", ["Junction", "edge"]).ref.channel == "temp3"
    assert find_channel(chip, "fan", ["edge"]) is None


def test_read_refuses_link_swapped_in_after_resolution(tmp_path, monkeypatch):
    fake = SysfsBuilder(tmp_path / "sys")
    nested = fake.root / "nested"
    nested.mkdir()
    (nested / "input").write_text("safe", encoding="ascii")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "input").write_text("outside", encoding="ascii")
    original_resolve = Path.resolve

    def resolve_then_swap(path, *args, **kwargs):
        resolved = original_resolve(path, *args, **kwargs)
        if path == nested / "input":
            nested.rename(fake.root / "moved")
            fake.link(nested, outside)
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_then_swap)
    read = Sysfs(fake.root).read_text("nested/input")

    assert read.value is None
    assert read.error is not None


def test_read_refuses_root_parent_swapped_after_resolution(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    parent.mkdir()
    fake = SysfsBuilder(parent / "sys")
    (fake.root / "input").write_text("safe", encoding="ascii")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_root = SysfsBuilder(outside / "sys")
    (outside_root.root / "input").write_text("outside", encoding="ascii")
    sysfs = Sysfs(fake.root)
    original_resolve = Path.resolve

    def resolve_then_swap(path, *args, **kwargs):
        resolved = original_resolve(path, *args, **kwargs)
        if path == fake.root / "input":
            parent.rename(tmp_path / "moved")
            fake.link(parent, outside)
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_then_swap)
    read = sysfs.read_text("input")

    assert read.value is None
    assert read.error is not None


def test_different_chip_names_on_one_pci_device_have_distinct_sensor_refs(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    gpu = fake.pci()
    fake.hwmon(gpu, 2, "amdgpu", {"temp1": (45000, "edge")})
    fake.hwmon(gpu, 9, "boardmon", {"temp1": (37000, "board")})

    first, second = enumerate_hwmon(Sysfs(fake.root))
    assert first.device_id == second.device_id == "pci/0000:03:00.0"
    first_channel, = first.channels
    second_channel, = second.channels

    assert first_channel.ref.channel == second_channel.ref.channel == "temp1"
    assert first_channel.ref.stable_id != second_channel.ref.stable_id


def test_recycled_hwmon_class_path_does_not_read_another_device(tmp_path):
    fake = SysfsBuilder(tmp_path / "sys")
    first = fake.pci()
    second = fake.pci("0000:05:00.0")
    old_chip_path = fake.hwmon(first, 2, "amdgpu", {"temp1": (45000, "edge")})
    sysfs = Sysfs(fake.root)
    old_chip, = enumerate_hwmon(sysfs)
    old_channel, = old_chip.channels
    assert sysfs.read_number(old_channel.input_path, 0.001).value == 45.0

    (fake.root / "class/hwmon/hwmon2").unlink()
    old_chip_path.rename(first / "removed-hwmon2")
    fake.hwmon(second, 2, "amdgpu", {"temp1": (93000, "edge")})
    new_chip, = enumerate_hwmon(sysfs)
    new_channel, = new_chip.channels

    assert old_channel.ref != new_channel.ref
    assert sysfs.read_number(new_channel.input_path, 0.001).value == 93.0
    stale = sysfs.read_number(old_channel.input_path, 0.001)
    assert stale.value is None
    assert stale.error is not None
