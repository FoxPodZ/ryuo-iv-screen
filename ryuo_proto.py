# ryuo-iv-screen -- control the ASUS ROG Ryuo IV cooler screen without ASUS software
# Copyright (C) 2026 FoxPodZ (foxpodz.de)  <https://github.com/foxpodz/ryuo-iv-screen>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ADDITIONAL TERM under GPLv3 section 7(b): you must preserve the author
# attribution "FoxPodZ (foxpodz.de)" and a link to the original repository in
# this file and in the Appropriate Legal Notices of any work that displays
# them.  See LICENSE-ADDITIONAL-TERMS.md.
"""
ryuo_proto.py — wire format for the ASUS ROG Ryuo IV screen (Baiyi "cm16" board)

USB: PID 0x1C76, interface 0 (MI_00) = HID. The VENDOR id is not stable across
firmware -- see VIDS below. Match on the product id.
     (sys.usb.config = "hid,adb")
Device side opens /dev/hidg0; host side is a hidraw node.

NOTE: 0B05:19AF is *not* this device -- that is the motherboard's Aura LED
Controller, which is easy to grab by mistake when you go looking for the
ASUS vendor ID.

Reconstructed from:
  SerialService.apk  com.baiyi.service.serialservice.serialdataservice
      SerialMsgManager.sendRequestMsg()   framing
      ByteTools.getCRC() / int2Bytes()    checksum + length encoding
      android_hidport_api.HidManage       transport + 1024-byte padding
  HomeUI.apk         com.baiyi.homeui.hshomeui
      entity/Pc*.java                     payload schema
      manage/MsgReceiverManager.java      command dispatch

--------------------------------------------------------------------------
FRAME
    5A | stuffed( LEN | BODY | CKSUM ) | 5A

    LEN    2 bytes BIG-ENDIAN, = len(BODY) + 5
    CKSUM  1 byte, = sum(LEN + BODY) & 0xFF     (additive sum, not a real CRC)
    stuffing (payload only, never the delimiters):
        0x5A -> 5B 01
        0x5B -> 5B 02
    Whole frame is then zero-padded to a multiple of 1024 before the HID write.

BODY — this is HTTP. They reimplemented HTTP over USB HID.

    request:    "<METHOD> <resource> 1\r\n"      e.g.  POST all 1
    response:   "<version> <status>\r\n"         e.g.  1 200
                "Key=Value\r\n" ...              DataHeader fields, "-1" omitted
                "\r\n"
                "<payload>"                      JSON, len == ContentLength

    METHOD  : GET | POST | DELETE | STATE
    Header keys: SeqNumber, AckNumber, ContentLength, ContentType,
                 FileName, FileSize, ContentRange, Counter, Date, msgId
    The device ACKs with AckNumber = your SeqNumber + 1.
    FileName/FileSize/ContentRange exist in DataHeader, but there is no
    working upload over HID on this firmware -- see "media files" below.
    Media goes on with adb. (MTP is not enabled.)
--------------------------------------------------------------------------
"""

from __future__ import annotations

import json

# Single source of truth for the device identity.
#
# The VENDOR id CHANGES BETWEEN FIRMWARE VERSIONS. Observed:
#
#   fw 1.0.3   0B05:1C76   ASUSTek        product "HID Interface"
#   fw 1.0.7   1C75:1C76   BYDevice/Baiyi product "HID Interface"
#   fw 1.0.10  0B05:1C76   ASUSTek        product "ROG RYUO IV Standard"
#
# So 1.0.7 is the odd one out: it shipped under the ODM's vendor id and later
# firmware went back to ASUS's. Anything matching on VID alone breaks on a
# firmware update, which is exactly what happened to this file.
#
# The PRODUCT id is stable across every version seen. Match on that.
#
# Careful: 0B05:19AF is NOT this device -- it is the motherboard's Aura LED
# controller. Since 0B05 is now also the cooler's vendor id, the product id is
# the ONLY thing separating them.
VID_BYDEVICE = 0x1C75
VID_ASUS = 0x0B05
VIDS = (VID_ASUS, VID_BYDEVICE)

VID = VID_ASUS         # default/most recent; prefer find_devices() over this
PID = 0x1C76           # stable across all known firmware -- the real identifier
INTERFACE = 0          # MI_00; the other USB interface is ADB, not HID


def find_devices(hid_module, vid: int | None = None, pid: int = PID) -> list:
    """Enumerate the screen without caring which vendor id the firmware uses.

    hidapi treats 0 as a wildcard, so enumerate(0, PID) finds the device under
    either vendor id. Pass an explicit vid to narrow it.
    """
    found = hid_module.enumerate(vid or 0, pid)
    if vid:
        return found
    return [d for d in found if d.get("vendor_id") in VIDS] or found

START = END = 0x5A
ESC = 0x5B
REPORT_SIZE = 1024

GET, POST, DELETE, STATE = "GET", "POST", "DELETE", "STATE"

# resources accepted by MsgReceiverManager
RES_ALL                 = "all"           # full PcInfo telemetry blob
RES_SPEC                = "spec"          # CPU/GPU model name strings
RES_SYSINFO_DISPLAY     = "sysinfoDisplay"
RES_CONFIG              = "config"
RES_PRESET              = "preset"
RES_ROTATE              = "rotate"
RES_BRIGHTNESS          = "brightness"
RES_POWER               = "power"
RES_TEMPERATURE         = "temperature"   # toggles Celsius/Fahrenheit
RES_DISPLAY_IN_SLEEP    = "displayInSleep"
RES_WATERFALL_MODE      = "waterfallMode"
RES_WATERBLOCK_SCREEN   = "waterBlockScreen"
RES_WATERBLOCK_SCREENID = "waterBlockScreenId"
RES_FAN_LCD             = "fanLCD"
RES_FAN_LCD_SET         = "fanLCDSet"
RES_UPGRADE             = "upgrade"
RES_DISCONN             = "disconn"       # host going away -> reverts to stock loop

# Handled inside SerialService itself. conn, mediaDelete include and the
# transport stub are confirmed on fw 1.0.10 (tests/probe.py conn_handshake,
# media_delete, transport_stub); mediaDelete exclude and turboPump are read
# from source. PROTOCOL.md §4.
RES_CONN                = "conn"          # handshake -> capability descriptor + media listing
RES_MEDIA_DELETE        = "mediaDelete"   # {"include": [...]} or {"exclude": [...]}
RES_TRANSPORT           = "transport"     # upload stub: replies, receives nothing (see below)
RES_TRANSPORTED         = "transported"   # no reply; type "firmware" pokes the updater
RES_TURBO_PUMP          = "turboPump"     # writes an aio_cooler I2C driver this board doesn't have


# ---------------------------------------------------------------- framing

def _stuff(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b == START:
            out += bytes((ESC, 0x01))
        elif b == ESC:
            out += bytes((ESC, 0x02))
        else:
            out.append(b)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    out, it = bytearray(), iter(data)
    for b in it:
        if b == ESC:
            nxt = next(it, None)
            if nxt == 0x01:
                out.append(START)
            elif nxt == 0x02:
                out.append(ESC)
            else:
                raise ValueError("bad escape 5B " +
                                 ("<truncated>" if nxt is None else f"{nxt:02X}"))
        else:
            out.append(b)
    return bytes(out)


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def build_body(start_line: str, content: str = "", *,
               seq: int | None = None, ack: int | None = None,
               **extra: object) -> bytes:
    # ContentLength is a BYTE count. json.dumps escapes non-ASCII by default so
    # the two coincide for anything request() builds, but build_body() takes an
    # arbitrary string, so measure the encoded form rather than the characters.
    fields: dict[str, object] = {"ContentType": "json",
                                 "ContentLength": len(content.encode())}
    if seq is not None:
        fields["SeqNumber"] = seq
    if ack is not None:
        fields["AckNumber"] = ack
    fields.update(extra)

    lines = [start_line] + [f"{k}={v}" for k, v in fields.items() if str(v) != "-1"]
    return ("\r\n".join(lines) + "\r\n\r\n" + content).encode()


def encode(body: bytes) -> bytes:
    length = (len(body) + 5).to_bytes(2, "big")
    inner = length + body
    inner += bytes((checksum(inner),))
    return bytes((START,)) + _stuff(inner) + bytes((END,))


def decode(frame: bytes) -> bytes:
    if len(frame) < 3 or frame[0] != START or frame[-1] != END:
        raise ValueError("missing 0x5A delimiters")
    inner = _unstuff(frame[1:-1])
    body, got, want = inner[2:-1], inner[-1], checksum(inner[:-1])
    if got != want:
        raise ValueError(f"checksum mismatch: got {got:#04x}, want {want:#04x}")
    if (declared := int.from_bytes(inner[:2], "big")) != len(body) + 5:
        raise ValueError(f"length mismatch: header {declared}, body {len(body)}")
    return body


def pad_for_hid(frame: bytes, size: int = REPORT_SIZE) -> bytes:
    rem = len(frame) % size
    return frame if rem == 0 else frame + bytes(size - rem)


def request(method: str, resource: str, payload: dict | None = None,
            *, seq: int | None = None) -> bytes:
    content = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
    body = build_body(f"{method} {resource} 1", content, seq=seq)
    return pad_for_hid(encode(body))


def reply_json(body: str | None):
    """The JSON payload of a decoded reply, or None if there isn't one."""
    if not body:
        return None
    content = body.partition("\r\n\r\n")[2].strip()
    try:
        return json.loads(content) if content else None
    except ValueError:
        return None


# ---------------------------------------------------------------- media files
# There is NO upload over HID on this firmware, whatever the resource names
# suggest. Confirmed on fw 1.0.10 unless marked:
#
#   transport    stores fileName / fileSize / type and replies
#                {"state": "success", "blockMaxSize": 888888888} -- but no
#                file is created and nothing ever receives data. A frame of
#                raw file data goes to the command parser, which finds no
#                headers and should throw (source only; never sent).
#   transported  replies nothing. For type "firmware" it asks RKUpdateService
#                to check for a local update package (source only).
#
# Get media onto the device with `adb push` to /sdcard/pcMedia/. What does
# work over HID is listing (`conn`) and deleting (`mediaDelete`).

def check_media_name(name: str) -> str:
    """Refuse anything but a bare file name.

    mediaDelete builds its path as "sdcard/pcMedia/" + name, so a name with a
    separator in it would reach outside pcMedia/.
    """
    if not name or name in (".", "..") or "\x00" in name:
        raise ValueError(f"bad media name {name!r}")
    if "/" in name or "\\" in name:
        raise ValueError(f"media name {name!r} has a path separator; "
                         f"only bare names in pcMedia/ are accepted")
    return name


def media_delete_payload(*, include: list[str] | None = None,
                         exclude: list[str] | None = None) -> dict:
    """Body of `POST mediaDelete`. Only ever deletes from sdcard/pcMedia/.

    include: delete exactly these.
    exclude: delete everything in pcMedia/ EXCEPT these -- how Info Hub
             syncs. An empty exclude list deletes all of it. The presets in
             pcMediaPreset/ are untouched either way.
    """
    if (include is None) == (exclude is None):
        raise ValueError("give exactly one of include= or exclude=")
    names = include if include is not None else exclude
    for n in names:
        check_media_name(n)
    return ({"include": list(include)} if include is not None
            else {"exclude": list(exclude)})


def redact_conn(info: dict) -> dict:
    """A copy of a `conn` reply with the serial number blanked, for pasting."""
    out = dict(info)
    if "sn" in out:
        out["sn"] = "<redacted>"
    return out


# ---------------------------------------------------------------- payloads
# GROUND TRUTH: captured from ASUS Info Hub via `adb logcat` on the device.
# These schemas are what Info Hub actually sends, not inferred from field types.

def pc_info(*, cpu=None, gpu=None, memory=None, network=None, disk=None,
            motherboard=None, fans=None, timestamp_ms=None) -> dict:
    """Body of `POST all`. Sent roughly once per second.

    Units matter:
      memory total/used  -> MEGABYTES  (e.g. 32768)
      disk   total/used  -> GIGABYTES  (e.g. 1000)
      speedAverage       -> MHz
      network up/down    -> KB/s
      timestamp          -> MILLISECONDS since epoch
      temperatures       -> always Celsius; the device converts for display
    """
    import time
    return {
        "network":  network or {"upload": 0, "download": 0},
        # total/used/load in MB / MB / %
        "memory":   memory or {"total": 0, "used": 0, "load": 0,
                               "temperature": 0, "speed": 0},
        "cpu":      cpu or {"load": 0, "temperature": 0, "temperaturePackage": 0,
                            "speedAverage": 0, "power": 0, "voltage": 0,
                            "usage": 0},
        "gpu":      gpu or {"hasDedicated": True, "load": 0, "temperature": 0,
                            "fan": 0, "speed": 0, "power": 0, "voltage": 0},
        "disk":     disk or {"total": 0, "used": 0, "load": 0, "activity": 0,
                             "temperature": 0, "readSpeed": 0, "writeSpeed": 0},
        # [{"onBoard": bool, "name": str, "value": rpm}]
        "fans":     fans or [],
        "motherboard": motherboard or {"temperature": 0, "chipsetTemperature": 0},
        "timestamp": timestamp_ms if timestamp_ms is not None
                     else int(time.time() * 1000),
    }


# Six fixed widget slots. Position on screen == index in this array;
# "" leaves the slot empty. This is what the Info Hub drag-and-drop produces.
SLOTS = 6

# The authoritative list, from HomeUI. An item only renders if it appears in
# BOTH maps: `subTitle` (item -> on-screen label) and the setInfoValue() calls
# in onRefreshUI() (item -> value). Anything in one but not the other gives you
# a label with no value, or a value with no label.
#
# "Fan CPU" / "Fan AIO Pump" / "Fan Chassis4" / "Fan Chassis 5" used to be in
# this list. Those exact strings are not real -- Info Hub's picker shows a
# "Fan Speed" heading with tiles labelled CPU / AIO Pump / Chassis 5 /
# Chassis4, and an earlier pass joined heading to label with the wrong word.
# The real prefix is "Fan Speed ", so fan_item("CPU") gives the working string.
#
# Items the renderer supports but Info Hub's UI has NO tile for:
#   GPU Power, Memory Utilization, Memory Frequency, Hard Disk Temperature,
#   and (probably) CPU Load / GPU Load, since the UI offers only "Usage".
SYSINFO_ITEMS = [
    "CPU Load", "CPU Usage", "CPU Temperature", "CPU Speed Average",
    "CPU Voltage",
    "GPU Load", "GPU Usage", "GPU Temperature", "GPU Speed", "GPU Power",
    "GPU Voltage",
    "Memory Utilization", "Memory Frequency",
    "Hard Disk Temperature", "Motherboard Temperature",
    "Date&Time",
]

# Have a value handler but NO subTitle entry, so they draw a value under a
# blank label. Half-implemented; listed for completeness, don't use them.
SYSINFO_ITEMS_UNLABELLED = ["GPU Frequency", "Date", "Time"]


def fan_item(name: str) -> str:
    """Item string for a fan readout -- and the escape hatch for arbitrary data.

    In HomeUI, onRefreshUI() registers a value for the item
    "Fan Speed " + fans[].name (unit RPM), and showInfo() draws, for any item
    starting with "Fan Speed" and longer than 10 chars, the substring from
    character 10 onward as the label.

    So the item string is "Fan Speed " + whatever you put in fans[].name, and
    the on-screen label is everything after character 10 -- i.e. the name you
    chose. You control both sides.

    That means any number you can measure on the host can be displayed under
    any label you like, which is the only way to get a readout ASUS's software
    cannot produce. The unit is always RPM.

        info  = pc_info(fans=[{"onBoard": True, "name": "Coolant", "value": 3229}])
        slots = sysinfo_slots(fan_item("Coolant"), "CPU Temperature")
    """
    return "Fan Speed " + name


def sysinfo_slots(*items: str) -> list[str]:
    """Pad an item list out to the 6 fixed slots."""
    out = list(items[:SLOTS])
    return out + [""] * (SLOTS - len(out))


# playMode. Two DIFFERENT comparisons decide behaviour, which is the trap:
#
#   onCompletion (main_video1): if playMode.equals("single") -> do nothing
#                               else -> post MSG_HANDEL_MEDIA (102)
#   case 102:                   "Single" -> replay media[0]
#                               "Random" -> random index
#                               "Cycle"  -> next index, wrapping
#                               anything else -> bare return, NO video set
#
# So an unrecognised string passes the first check and then silently falls
# through the second, leaving the player with no path = black screen.
# Only these three values work; they are the Info Hub UI's three modes.
PLAY_SINGLE = "Single"   # Single-Repeat: loop media[0]
PLAY_RANDOM = "Random"   # Shuffle:       random pick each time
PLAY_CYCLE  = "Cycle"    # Repeat-All:    walk media[] in order, wrapping
PLAY_MODES = [PLAY_SINGLE, PLAY_RANDOM, PLAY_CYCLE]

# screenMode. "Full Screen" is the single-zone path; ANY other string takes the
# split branch, where media/playMode become two-element lists (one per zone).
# "Screen Splitting" is the exact string Info Hub sends -- captured in
# captures/infohub-split-capture.log.
# Panel is 2240x1080 (physically portrait 1080x2240, rotated 90 deg by
# SurfaceFlinger). Split mode tiles it as 1606x1080 + 634x1080, read straight
# off the app's layout resource: main_parent is a horizontal LinearLayout whose
# home_layout2 is a hardcoded 634px and whose home_layout1 is layout_width=0dip
# with layout_weight=1.0 -- i.e. zone 1 is simply the remainder.
#
# Info Hub's own crop tool enforces aspect ratios matching a clean 1600/640,
# so ASUS's tooling and ASUS's layout disagree by 6px. It doesn't show, because
# main_img1 uses scaleType=FIT_XY and stretches whatever it gets to fill.
PANEL = (2240, 1080)
ZONE1 = (1606, 1080)   # main face -- LinearLayout remainder
ZONE2 = (634, 1080)    # strip past the bend -- hardcoded in the layout

MODE_FULL  = "Full Screen"
MODE_SPLIT = "Screen Splitting"   # exact string Info Hub sends

# setLayout1Path dispatches on file extension:
#   .mp4 -> VideoView, advances when the clip ends
#   .gif -> Fresco one-shot, advances when the gif ends
#   else -> Glide still image, advances after a hardcoded 7000 ms
# Missing files are skipped (it just posts "play next"), and playlists may mix
# all three freely.
STILL_SECONDS = 7


def _local_tz() -> str:
    """The host's IANA zone, e.g. 'Europe/Berlin'.

    The device wants an IANA name for its Date&Time widget. The stdlib alone
    can't give us one: datetime.now().astimezone().tzinfo is a fixed-offset
    timezone named 'CEST', never 'Europe/Berlin', on every Linux host. So look
    where the zone is actually configured -- $TZ, the /etc/localtime symlink,
    /etc/timezone -- and only then give up and use UTC. Pass time_zone=
    explicitly if none of those apply (Windows, containers).
    """
    import os
    cands = []
    tz = os.environ.get("TZ", "")
    cands.append(tz[1:] if tz.startswith(":") else tz)
    try:
        # /etc/localtime -> /usr/share/zoneinfo/Europe/Berlin
        link = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in link:
            cands.append(link.split("zoneinfo/", 1)[1])
    except OSError:
        pass
    try:
        with open("/etc/timezone") as f:          # Debian and friends
            cands.append(f.read().strip())
    except OSError:
        pass
    try:
        from datetime import datetime
        tz = datetime.now().astimezone().tzinfo   # zoneinfo objects have .key
        cands.append(getattr(tz, "key", None) or "")
    except Exception:
        pass
    for name in cands:
        if name and "/" in name and not name.startswith("posix/"):
            return name
    return "UTC"


def screen_config(*, config_id="Customization", screen_mode=None,
                  play_mode=PLAY_SINGLE, media=None, sysinfo=None,
                  media2=None, play_mode2=None,
                  title_color="#E5252B", content_color="#FFFFFF",
                  title_color2=None, content_color2=None,
                  opacity=100, time_zone=None) -> dict:
    """The ScreenConfig object (goes in waterBlockScreen.id).

    Single zone:  media=["a.mp4"],  play_mode="Single"
    Split zones:  media=["a.mp4"], media2=["b.png"] -> the wire format becomes
                  media=[[...],[...]] and playMode=[mode1, mode2], which is
                  what the split branch of case 105 casts them to.

    Filenames only; the app resolves the directory itself (names starting with
    "RYUO" -> /sdcard/pcMediaPreset/, everything else -> /sdcard/pcMedia/).
    """
    split = media2 is not None
    if screen_mode is None:
        screen_mode = MODE_SPLIT if split else MODE_FULL
    def _settings(title, content):
        return {"titleColor": title, "contentColor": content,
                "filter": {"value": None, "opacity": opacity}, "badges": []}

    if split:
        # media, playMode AND settings all become two-element lists, one per
        # zone. sysinfoDisplay stays a flat 6-slot array (3 per zone).
        wire_media = [list(media or []), list(media2)]
        wire_mode = [play_mode, play_mode2 or play_mode]
        wire_settings = [_settings(title_color, content_color),
                         _settings(title_color2 or title_color,
                                   content_color2 or content_color)]
    else:
        wire_media = list(media or [])
        wire_mode = play_mode
        wire_settings = _settings(title_color, content_color)

    return {
        "id": config_id,
        "screenMode": screen_mode,
        "playMode": wire_mode,
        "media": wire_media,
        # titleColor = the "CPU:" label; contentColor = the value.
        # Color.parseColor(), so #RRGGBB or #AARRGGBB both work.
        "settings": wire_settings,
        "sysinfoDisplay": sysinfo if sysinfo is not None else sysinfo_slots(),
        "timeZone": time_zone or _local_tz(),
    }


def preset_payload(sysinfo: list[str], *, title_color="#E5252B",
                   content_color="#FFFFFF", opacity=100) -> dict:
    """Body of `POST preset` — the LIVE-UPDATE channel.

    MainActivity case 114 only calls setSysinfoDisplay/setSettings, repaints
    the text views and returns. Unlike `config` (case 105) it does NOT hide
    mainParent or tear down the video player, so it is safe to send at speed
    while media keeps playing underneath.

    Colours go through Color.parseColor(), which also accepts #AARRGGBB.
    """
    return {
        "id": "Customization",
        "sysinfoDisplay": sysinfo,
        "settings": {"titleColor": title_color,
                     "contentColor": content_color,
                     "filter": {"value": None, "opacity": opacity},
                     "badges": []},
    }


def hsv_hex(hue: float, sat: float = 1.0, val: float = 1.0) -> str:
    """hue in [0,1) -> '#RRGGBB'."""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, sat, val)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


# Temperature -> colour. The number in each tuple is the EXCLUSIVE UPPER bound:
# t < 34 blue, 34 <= t < 61 green, 61 <= t < 81 yellow, 81 <= t < 96 red.
THERMAL_BANDS = [
    (34,  "#2E6BFF"),   # cool      blue
    (61,  "#22C55E"),   # normal    green
    (81,  "#EAB308"),   # warm      yellow
    (96,  "#EF4444"),   # hot       red
]
THERMAL_ALERT = ("#FF6B6B", "#7F1D1D")   # >=96C: alternates light/dark red


def thermal_hex(temp: float, phase: bool = False) -> str:
    """Colour for a temperature in Celsius. `phase` flips the alert blink."""
    for limit, colour in THERMAL_BANDS:
        if temp < limit:
            return colour
    return THERMAL_ALERT[1 if phase else 0]


def config_payload(*, unit="Celsius", enable=True, display_in_sleep=True,
                   brightness=85, config=None, fan_lcd=None,
                   cpu_name="", gpu_name="") -> dict:
    """Body of `POST config` — the full session setup Info Hub sends on connect."""
    return {
        "temperature": unit,                       # "Celsius" | "Fahrenheit"
        "waterBlockScreen": {
            "enable": enable,
            "displayInSleep": display_in_sleep,
            "brightness": brightness,              # 0-102; 100 is ~98% of max
            "id": config or screen_config(),
            "fanLCD": fan_lcd or {"speed": "", "mode": ""},
        },
        "spec": {"cpu": cpu_name, "gpu": gpu_name},
    }


if __name__ == "__main__":
    cfg = config_payload(
        brightness=85,
        cpu_name="<host CPU model>",
        gpu_name="<host GPU model>",
        config=screen_config(
            media=["RYUO_IV_HW_Info_02.mp4"],
            sysinfo=sysinfo_slots("CPU Temperature", "GPU Temperature", "Date&Time"),
        ),
    )
    f = request(POST, RES_CONFIG, cfg, seq=1)
    print("config frame:", len(f), "bytes")
    print(decode(f.rstrip(b"\x00")).decode()[:600])
