#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 FoxPodZ (foxpodz.de)
"""
Codec tests for ryuo_proto. No hardware needed — pure wire-format checks.

    pip install pytest
    pytest tests/ -v

The golden vector below is the same worked example printed in PROTOCOL.md §2.
If this test fails, either the code changed or the doc is lying. Both matter.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ryuo_proto as proto


# --------------------------------------------------------------- golden vector

GOLDEN_GET_SPEC = bytes.fromhex(
    "5A 00 43 47 45 54 20 73 70 65 63 20 31 0D 0A 43"
    "6F 6E 74 65 6E 74 54 79 70 65 3D 6A 73 6F 6E 0D"
    "0A 43 6F 6E 74 65 6E 74 4C 65 6E 67 74 68 3D 30"
    "0D 0A 53 65 71 4E 75 6D 62 65 72 3D 31 0D 0A 0D"
    "0A D0 5A".replace(" ", "")
)


def test_worked_example_matches_protocol_md():
    """PROTOCOL.md §2 prints this exact hex dump. Keep them in sync."""
    built = proto.request(proto.GET, "spec", seq=1).rstrip(b"\x00")
    assert built == GOLDEN_GET_SPEC


def test_worked_example_fields():
    assert len(GOLDEN_GET_SPEC) == 67
    assert int.from_bytes(GOLDEN_GET_SPEC[1:3], "big") == 67      # LEN
    assert GOLDEN_GET_SPEC[-2] == 0xD0                            # CKSUM
    body = proto.decode(GOLDEN_GET_SPEC)
    assert int.from_bytes(GOLDEN_GET_SPEC[1:3], "big") == len(body) + 5


# --------------------------------------------------------------------- framing

@pytest.mark.parametrize("payload", [
    b"",
    b"\x5a" * 8,                      # all start/end delimiters
    b"\x5b" * 8,                      # all escapes
    b"\x5a\x5b\x5a\x5b",              # alternating
    bytes(range(256)),                # every byte value
    b'{"media":["a.mp4"],"badges":[]}',   # realistic: '[' IS 0x5B
    b"x" * 5000,                      # multi-report
])
def test_encode_decode_roundtrip(payload):
    assert proto.decode(proto.encode(payload)) == payload


def test_stuffing_removes_delimiters_from_interior():
    frame = proto.encode(b"\x5a\x5b")
    assert frame[0] == proto.START and frame[-1] == proto.END
    assert proto.START not in frame[1:-1], "raw 0x5A leaked into the payload"


def test_stuffing_exact_bytes():
    """0x5A becomes 5B 01 -- and that new 5B must not be escaped again."""
    assert proto._stuff(b"\x5a") == b"\x5b\x01"
    assert proto._stuff(b"\x5b") == b"\x5b\x02"
    assert proto._stuff(b"\x5a\x5b\x5a") == b"\x5b\x01\x5b\x02\x5b\x01"


def test_checksum_is_additive_sum_not_crc():
    body = b"hello"
    inner = (len(body) + 5).to_bytes(2, "big") + body
    assert proto.checksum(inner) == sum(inner) & 0xFF


def test_decode_rejects_bad_checksum():
    frame = bytearray(proto.encode(b"payload"))
    frame[-2] ^= 0xFF
    with pytest.raises(ValueError, match="checksum"):
        proto.decode(bytes(frame))


def test_decode_rejects_missing_delimiters():
    with pytest.raises(ValueError, match="delimiter"):
        proto.decode(b"\x00\x01\x02")


def test_decode_rejects_bad_escape():
    with pytest.raises(ValueError, match="bad escape"):
        proto.decode(b"\x5a\x5b\x09\x5a")


def test_decode_rejects_truncated_escape():
    # an escape byte with nothing after it must still be a ValueError,
    # not a TypeError from formatting None
    with pytest.raises(ValueError, match="bad escape"):
        proto.decode(b"\x5a\x5b\x5a")


def test_local_tz_is_iana_or_utc():
    name = proto._local_tz()
    assert name == "UTC" or "/" in name


def test_padding_is_multiple_of_report_size():
    for n in (1, 100, 1023, 1024, 1025, 4000):
        padded = proto.pad_for_hid(proto.encode(b"x" * n))
        assert len(padded) % proto.REPORT_SIZE == 0


# -------------------------------------------------------------------- payloads

def test_content_length_is_a_byte_count():
    """The header counts bytes, not characters. json.dumps hides this by
    escaping non-ASCII, but build_body() takes any string."""
    body = proto.build_body("POST all 1", "\u00fc", seq=1)   # 1 char, 2 bytes
    assert b"ContentLength=2" in body


def test_minus_one_fields_are_omitted():
    body = proto.build_body("GET spec 1", "", seq=1, AckNumber=-1).decode()
    assert "AckNumber" not in body
    assert "SeqNumber=1" in body


def test_sysinfo_always_six_slots():
    assert proto.sysinfo_slots() == [""] * 6
    assert len(proto.sysinfo_slots("CPU Temperature")) == 6
    # overflow is truncated, not an error
    assert len(proto.sysinfo_slots(*["CPU Temperature"] * 10)) == 6


def test_full_screen_shape():
    cfg = proto.screen_config(media=["a.mp4"])
    assert cfg["screenMode"] == proto.MODE_FULL
    assert cfg["media"] == ["a.mp4"]
    assert isinstance(cfg["playMode"], str)
    assert isinstance(cfg["settings"], dict)


def test_split_shape_matches_captured_frame():
    """captures/infohub-split-capture.log:

       screenMode='Screen Splitting', playMode=[Single, Single],
       media=[[a.png], [b.png]], settings=[{...}, {...}],
       sysinfoDisplay=[CPU Temperature, GPU Temperature, , , , ]
    """
    cfg = proto.screen_config(media=["a.png"], media2=["b.png"])
    assert cfg["screenMode"] == "Screen Splitting"
    assert cfg["media"] == [["a.png"], ["b.png"]]
    assert cfg["playMode"] == ["Single", "Single"]
    assert isinstance(cfg["settings"], list) and len(cfg["settings"]) == 2
    # sysinfoDisplay stays FLAT in split mode — this is the easy one to get wrong
    assert len(cfg["sysinfoDisplay"]) == 6
    assert not isinstance(cfg["sysinfoDisplay"][0], list)


def test_only_three_play_modes_exist():
    assert proto.PLAY_MODES == ["Single", "Random", "Cycle"]
    # lowercase is the trap documented in §7 — must not be a valid mode
    assert "single" not in proto.PLAY_MODES


def test_pc_info_has_every_key_info_hub_sends():
    """Info Hub sends all keys even when it has no value. See §10."""
    info = proto.pc_info()
    assert set(info) == {"network", "memory", "cpu", "gpu", "disk",
                         "fans", "motherboard", "timestamp"}
    assert set(info["cpu"]) == {"load", "temperature", "temperaturePackage",
                                "speedAverage", "power", "voltage", "usage"}
    # gpu has no "usage" key even though cpu does — matches the capture
    assert "usage" not in info["gpu"]
    assert "hasDedicated" in info["gpu"]


def test_config_payload_shape():
    cfg = proto.config_payload(brightness=85)
    assert cfg["waterBlockScreen"]["brightness"] == 85
    assert set(cfg) == {"temperature", "waterBlockScreen", "spec"}


# -------------------------------------------------------------------- thermals

@pytest.mark.parametrize("temp,expected", [
    (0, "#2E6BFF"), (33, "#2E6BFF"),        # cool
    (34, "#22C55E"), (60, "#22C55E"),       # normal
    (61, "#EAB308"), (80, "#EAB308"),       # warm
    (81, "#EF4444"), (95, "#EF4444"),       # hot
])
def test_thermal_bands(temp, expected):
    assert proto.thermal_hex(temp) == expected


def test_thermal_alert_blinks():
    assert proto.thermal_hex(96, phase=False) != proto.thermal_hex(96, phase=True)


def test_hsv_hex_is_valid_colour():
    for h in (0.0, 0.25, 0.5, 0.99):
        c = proto.hsv_hex(h)
        assert len(c) == 7 and c[0] == "#"
        int(c[1:], 16)


def test_fake_fan_items_are_gone():
    """These four were in the list for weeks and do not exist in the renderer."""
    for fake in ("Fan CPU", "Fan AIO Pump", "Fan Chassis4", "Fan Chassis 5"):
        assert fake not in proto.SYSINFO_ITEMS


def test_item_list_matches_renderer():
    assert "Hard Disk Temperature" in proto.SYSINFO_ITEMS
    assert len(proto.SYSINFO_ITEMS) == 16
    # items with a value handler but no subTitle entry must stay out
    for half in proto.SYSINFO_ITEMS_UNLABELLED:
        assert half not in proto.SYSINFO_ITEMS


def test_fan_item_label_slicing():
    """showInfo draws info.substring(10), so the label is exactly the name."""
    for name in ("Coolant", "CPU", "NAS Bay 3", "x"):
        item = proto.fan_item(name)
        assert item.startswith("Fan Speed")
        assert len(item) > 10, "label slice needs length > 10 to render"
        assert item[10:] == name


# ----------------------------------------------------------------- media files

@pytest.mark.parametrize("name", [
    "", ".", "..", "a/b.mp4", "..\\b.mp4", "../pcMediaPreset/RYUO_x.mp4",
    "a\x00b",
])
def test_bad_media_names_refused(name):
    """mediaDelete joins "sdcard/pcMedia/" + name, so a separator escapes it."""
    with pytest.raises(ValueError):
        proto.check_media_name(name)
    with pytest.raises(ValueError):
        proto.media_delete_payload(include=[name])


@pytest.mark.parametrize("name", ["my clip (2).mp4", "RYUO_mine.mp4", "ryuo.png"])
def test_good_media_names_pass(name):
    """RYUO* only matters to the player's lookup, not to mediaDelete."""
    assert proto.check_media_name(name) == name


def test_media_delete_takes_exactly_one_mode():
    assert proto.media_delete_payload(include=["a.mp4"]) == {"include": ["a.mp4"]}
    assert proto.media_delete_payload(exclude=["k.mp4"]) == {"exclude": ["k.mp4"]}
    with pytest.raises(ValueError):
        proto.media_delete_payload()
    with pytest.raises(ValueError):
        proto.media_delete_payload(include=["a"], exclude=["b"])


def test_redact_conn_hides_serial_only():
    info = {"sn": "TC0000", "OS": "Android", "productId": "cm16"}
    out = proto.redact_conn(info)
    assert out["sn"] != "TC0000" and out["productId"] == "cm16"
    assert info["sn"] == "TC0000", "must not modify the caller's dict"


def test_reply_json():
    body = "1 200\r\nAckNumber=2\r\n\r\n{\"state\":\"success\"}"
    assert proto.reply_json(body) == {"state": "success"}
    assert proto.reply_json("1 200\r\n\r\n") is None
    assert proto.reply_json(None) is None
    assert proto.reply_json("1 200\r\n\r\nnot json") is None


def test_device_identity():
    """The 0B05:19AF mixup cost real time. Pin it.

    The VENDOR id is firmware-dependent (0B05 on 1.0.3 and 1.0.10, 1C75 on
    1.0.7), so only the product id is worth pinning. 19AF is the motherboard's
    Aura controller and shares 0B05 with the cooler -- the product id is the
    only thing telling them apart.
    """
    assert proto.PID == 0x1C76
    assert set(proto.VIDS) == {0x0B05, 0x1C75}
    assert proto.PID != 0x19AF
    assert proto.PANEL == (2240, 1080)
    assert proto.ZONE1[0] + proto.ZONE2[0] == proto.PANEL[0]
    # read off the layout resource: home_layout2 is a hardcoded 634px,
    # home_layout1 is layout_weight=1.0 and takes the remainder.
    assert proto.ZONE2[0] == 634
    assert proto.ZONE1[0] == 1606
