#!/usr/bin/env python3
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
ryuo_send.py — drive the ASUS ROG Ryuo IV screen with no ASUS software.

    pip install hidapi psutil
    (close ASUS Info Hub first — it holds the HID handle)

    python ryuo_send.py --list
    python ryuo_send.py --config-only --items "CPU Temperature" "GPU Temperature" "Date&Time"
    python ryuo_send.py --items "CPU Temperature" "GPU Temperature" "Date&Time"

Sends `POST config` once (widgets, brightness, CPU/GPU names, media), then
`POST all` every --interval seconds. The device reverts to standby.mp4 if it
stops hearing from us for ~10 s, so the loop is the keepalive.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import time

import hid

import ryuo_proto as proto

VID, PID = proto.VID, proto.PID


# ------------------------------------------------------------------ transport

def open_device(vid: int | None, pid: int, index: int | None = None):
    # vid=None means "any vendor id with this product id" -- the vendor id
    # changes between firmware versions, the product id does not.
    devs = proto.find_devices(hid, vid, pid)
    if not devs:
        ids = f"{vid:04X}:{pid:04X}" if vid else f"????:{pid:04X}"
        sys.exit(f"no HID device {ids} — cooler unplugged, "
                 f"or Info Hub still running?")

    if index is not None:
        if not 0 <= index < len(devs):
            sys.exit(f"--index {index} out of range: {len(devs)} interface(s) "
                     f"enumerated, use --list to see them")
        pick = devs[index]
    else:
        # prefer the documented interface; fall back to whatever enumerated
        pick = next((d for d in devs
                     if d.get("interface_number") == proto.INTERFACE), devs[0])
        if len(devs) > 1:
            print(f"note: {len(devs)} interfaces enumerated, using "
                  f"interface_number={pick.get('interface_number')} "
                  f"(--list to see all, --index N to override)")

    h = hid.device()
    h.open_path(pick["path"])
    h.set_nonblocking(1)
    return h


def txn(h, method, resource, payload, seq, timeout=0.4, verbose=False):
    frame = proto.request(method, resource, payload, seq=seq)
    for off in range(0, len(frame), proto.REPORT_SIZE):
        chunk = frame[off:off + proto.REPORT_SIZE].ljust(proto.REPORT_SIZE, b"\x00")
        if h.write(b"\x00" + chunk) < 0:
            raise OSError("HID write failed")

    buf, deadline = bytearray(), time.time() + timeout
    while time.time() < deadline:
        data = h.read(proto.REPORT_SIZE)
        if data:
            buf += bytes(data)
            if buf.count(proto.START) >= 2:
                s = buf.index(proto.START)
                e = buf.index(proto.END, s + 1)
                try:
                    body = proto.decode(bytes(buf[s:e + 1])).decode(errors="replace")
                except ValueError as ex:
                    # a mangled reply is not worth killing the keepalive over
                    if verbose:
                        print(f"   <-- undecodable reply ({ex})")
                    return None
                if verbose:
                    print("   <--", body.split("\r\n")[0])
                return body
        else:
            time.sleep(0.01)
    return None


# ------------------------------------------------------------------ telemetry

def _cpu_name() -> str:
    if platform.system() == "Windows":
        return platform.processor() or "CPU"
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "CPU"


_NVIDIA_SMI: str | None | bool = False      # False = not looked up yet


def _nvidia() -> dict:
    """GPU stats via nvidia-smi, if present.

    Call this EVERY telemetry tick. It used to be called once before the main
    loop and the result reused for the lifetime of the process, which froze
    every GPU field -- temperature, load, clock, power -- at whatever it read
    at startup. The panel looked alive because the CPU figures next to it kept
    moving.

    Only the executable lookup is cached; the query itself is re-run.
    """
    global _NVIDIA_SMI
    if _NVIDIA_SMI is False:
        _NVIDIA_SMI = shutil.which("nvidia-smi")
    if not _NVIDIA_SMI:
        return {}
    q = ("name,temperature.gpu,utilization.gpu,power.draw,"
         "clocks.current.graphics,fan.speed")
    try:
        out = subprocess.run(
            [_NVIDIA_SMI, f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2).stdout.strip().split("\n")[0]
        name, temp, util, power, clock, fan = [x.strip() for x in out.split(",")]
    except Exception:
        return {}

    # nvidia-smi prints "[N/A]" for anything the card can't report -- fan speed
    # on laptops and passively cooled cards, power.draw on a lot of older GPUs.
    # One unparseable field must not take the whole GPU with it, so each one
    # degrades to 0 on its own.
    def _num(x: str) -> int:
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return 0

    return {"name": name,
            "stats": {"hasDedicated": True,
                      "load": _num(util), "temperature": _num(temp),
                      "fan": _num(fan), "speed": _num(clock),
                      "power": _num(power), "voltage": 0}}


def _cpu_temp(psutil) -> tuple[float, float]:
    """(temperature, temperaturePackage) in Celsius."""
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return 0.0, 0.0
    for key in ("k10temp", "zenpower", "coretemp", "acpitz"):
        if temps.get(key):
            entries = temps[key]
            cur = float(entries[0].current)
            pkg = cur
            for e in entries:
                if e.label and ("package" in e.label.lower() or "tctl" in e.label.lower()):
                    pkg = float(e.current)
            return cur, pkg
    return 0.0, 0.0


def collect(psutil, gpu: dict, extra_readouts: dict | None = None) -> dict:
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/" if platform.system() != "Windows" else "C:\\")
    freq = psutil.cpu_freq()
    load = psutil.cpu_percent()
    t, tpkg = _cpu_temp(psutil)

    fans = []
    try:
        for name, entries in (psutil.sensors_fans() or {}).items():
            for e in entries:
                fans.append({"onBoard": True, "name": e.label or name,
                             "value": int(e.current)})
    except Exception:
        pass

    # Arbitrary labelled readouts. The screen renders any fans[] entry as
    # "Fan Speed <name>", labelled with <name>, so this smuggles any number
    # you can measure onto the panel. See proto.fan_item().
    for label, value in (extra_readouts or {}).items():
        fans.append({"onBoard": True, "name": label, "value": int(value)})

    return proto.pc_info(
        cpu={"load": int(load), "temperature": round(t), "temperaturePackage": round(tpkg),
             "speedAverage": int(freq.current) if freq else 0,
             "power": 0, "voltage": 0, "usage": int(load)},
        gpu=gpu.get("stats") or {"hasDedicated": False, "load": 0, "temperature": 0,
                                 "fan": 0, "speed": 0, "power": 0, "voltage": 0},
        memory={"total": vm.total // (1024 ** 2),      # MB
                "used": vm.used // (1024 ** 2),
                "load": int(vm.percent), "temperature": 0, "speed": 0},
        disk={"total": du.total // (1024 ** 3),        # GB
              "used": du.used // (1024 ** 3),
              "load": int(du.percent), "activity": 0,
              "temperature": 0, "readSpeed": 0, "writeSpeed": 0},
        network={"upload": 0, "download": 0},
        motherboard={"temperature": 0, "chipsetTemperature": 0},
        fans=fans,
    )


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=None,
                    help="pin a vendor id; default is to accept any, since it "
                         "changes between firmware versions (0B05 on 1.0.3 and "
                         "1.0.10, 1C75 on 1.0.7)")
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=PID)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--index", type=int, default=None,
                    help="which enumerated interface to open (see --list); "
                         f"default: the one with interface_number={proto.INTERFACE}")
    ap.add_argument("--config-only", action="store_true",
                    help="push the config and exit (screen reverts after ~10s)")
    ap.add_argument("--items", nargs="*",
                    default=["CPU Temperature", "GPU Temperature", "Date&Time"],
                    help="up to 6; slot order == on-screen position")
    ap.add_argument("--readout", action="append", metavar="LABEL=VALUE",
                    default=[],
                    help="arbitrary labelled readout, e.g. --readout "
                         "Coolant=3229. Injected into fans[] so the panel "
                         "renders item 'Fan Speed <LABEL>' with the label "
                         "<LABEL> and unit RPM. Repeatable. The only way to "
                         "show a number ASUS's software can't produce.")
    ap.add_argument("--brightness", type=int, default=85,
                    help="0-102. Note 100 is only ~98%% of maximum: the value "
                         "is scaled by ~2.5 into a kernel backlight that clamps "
                         "at 255, so full brightness needs 102. Info Hub's own "
                         "default is 85.")
    ap.add_argument("--media", nargs="*", default=[],
                    help="filenames in /sdcard/pcMedia/ (custom) or "
                         "/sdcard/pcMediaPreset/ (names starting with RYUO)")
    ap.add_argument("--play-mode", default=proto.PLAY_SINGLE,
                    choices=proto.PLAY_MODES,
                    help="Single = repeat media[0], Random = shuffle, "
                         "Cycle = walk the playlist")
    ap.add_argument("--media2", nargs="*", default=None,
                    help="second zone's playlist; enables split-screen mode")
    ap.add_argument("--play-mode2", default=None, choices=proto.PLAY_MODES,
                    help="play mode for the second zone (default: same as zone 1)")
    ap.add_argument("--title-color2", default=None,
                    help="zone 2 label colour (default: same as zone 1)")
    ap.add_argument("--content-color2", default=None,
                    help="zone 2 value colour (default: same as zone 1)")
    ap.add_argument("--screen-mode", default=None,
                    help='override screenMode (default "Full Screen", or '
                         '"Screen Splitting" when --media2 is given)')
    ap.add_argument("--shuffle", action="store_true",
                    help="alias for --play-mode Random")
    ap.add_argument("--demo-temp", type=float, default=None,
                    help="force a temperature for testing --rgb-mode thermal; "
                         "pass a NEGATIVE value (e.g. -1) to sweep 20->100C "
                         "over 40s so every band is visible")
    ap.add_argument("--title-color", default="#E5252B",
                    help='colour of the labels ("CPU:"), hex e.g. "#00FF9C"')
    ap.add_argument("--content-color", default="#FFFFFF",
                    help='colour of the values, hex e.g. "#FFFFFF"')
    ap.add_argument("--opacity", type=int, default=100,
                    help="media dimming filter, 0-100")
    ap.add_argument("--rgb", choices=["title", "value", "both", "off"],
                    default="off",
                    help="which text to colour dynamically")
    ap.add_argument("--rgb-mode", choices=["hue", "thermal"], default="hue",
                    help="hue = rainbow cycle; thermal = colour by temperature")
    ap.add_argument("--rgb-source", choices=["cpu", "gpu"], default="cpu",
                    help="which temperature drives --rgb-mode thermal")
    ap.add_argument("--rgb-speed", type=float, default=0.2,
                    help="full hue rotations per second (default 0.2 = 5s)")
    ap.add_argument("--rgb-fps", type=float, default=10.0,
                    help="preset pushes per second while cycling")
    ap.add_argument("--timezone", default=None,
                    help="IANA zone for the Date&Time widget; "
                         "defaults to the host's")
    ap.add_argument("--unit", default="Celsius", choices=["Celsius", "Fahrenheit"])
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.list:
        found = proto.find_devices(hid, args.vid, args.pid)
        if not found:
            ids = (f"{args.vid:04X}:{args.pid:04X}" if args.vid
                   else f"any vendor with product {args.pid:04X}")
            print(f"nothing enumerating as {ids}")
        for i, d in enumerate(found):
            print(f"[{i}] usage_page={d.get('usage_page'):#06x} "
                  f"iface={d.get('interface_number')} "
                  f"product={d.get('product_string')!r}")
        return

    try:
        import psutil
    except ImportError:
        sys.exit("pip install psutil")

    if len(args.items) > proto.SLOTS:
        print(f"note: {len(args.items)} items given but the panel has "
              f"{proto.SLOTS} slots; ignoring {args.items[proto.SLOTS:]}")
    if args.interval > 5:
        print(f"WARNING: --interval {args.interval} is longer than the device "
              f"tolerates between POST all frames; the screen will revert "
              f"to stock between ticks. Keep it at ~1s.")

    media = list(args.media)
    play_mode = args.play_mode
    if args.shuffle:
        play_mode = proto.PLAY_RANDOM

    gpu = _nvidia()
    readouts = {}
    for spec in args.readout:
        if "=" not in spec:
            sys.exit(f"--readout needs LABEL=VALUE, got {spec!r}")
        label, _, value = spec.partition("=")
        label = label.strip()
        try:
            readouts[label] = int(float(value))
        except ValueError:
            sys.exit(f"--readout value must be a number, got {value!r}")
        if proto.fan_item(label) not in (args.items or []):
            print(f'note: --readout {label} has no matching item, so it will '
                  f'not be drawn. Add --items "{proto.fan_item(label)}".')

    h = open_device(args.vid, args.pid, args.index)
    seq = 1

    cfg = proto.config_payload(
        unit=args.unit,
        brightness=args.brightness,
        cpu_name=_cpu_name(),
        gpu_name=gpu.get("name", ""),
        config=proto.screen_config(
            media=media,
            play_mode=play_mode,
            media2=args.media2,
            play_mode2=args.play_mode2,
            title_color2=args.title_color2,
            content_color2=args.content_color2,
            screen_mode=args.screen_mode,
            sysinfo=proto.sysinfo_slots(*args.items),
            title_color=args.title_color,
            content_color=args.content_color,
            opacity=args.opacity,
            time_zone=args.timezone,
        ),
    )
    ap_settle = 1.6   # case 14 does postDelayed(doBlockScreen, 1000L)
    txn(h, proto.POST, proto.RES_CONFIG, cfg, seq, verbose=True)
    print(f"config pushed: slots={proto.sysinfo_slots(*args.items)} "
          f"brightness={args.brightness} "
          f"title={args.title_color} content={args.content_color}")
    if args.media2 is not None:
        print(f"split: zone1 ({play_mode}) {media}  |  "
              f"zone2 ({args.play_mode2 or play_mode}) {args.media2}")
    elif media:
        print(f"playlist ({play_mode}): {media}")
    elif play_mode != proto.PLAY_SINGLE:
        print(f"WARNING: --play-mode {play_mode} with an empty media list will "
              f"black-screen. Pass --media <files in /sdcard/pcMedia/>.")
    seq += 1

    if args.config_only:
        time.sleep(ap_settle)
        h.close()
        return

    # let the video player finish re-initialising before we touch anything else
    time.sleep(ap_settle)

    slots = proto.sysinfo_slots(*args.items)
    if args.rgb != "off":
        print(f"rgb: {args.rgb} @ {args.rgb_speed}/s, {args.rgb_fps} pushes/s")
    print("looping (ctrl-c to stop)...")

    started = time.time()
    next_stats = 0.0
    last_stats = None
    try:
        while True:
            now = time.time()

            # telemetry on its own cadence
            if now >= next_stats:
                # re-poll the GPU every tick; `gpu` from before the loop is
                # only a fallback for when nvidia-smi isn't there at all
                last_stats = collect(psutil, _nvidia() or gpu, readouts)
                reply = txn(h, proto.POST, proto.RES_ALL, last_stats,
                            seq, verbose=args.verbose)
                if args.verbose:
                    print(f"seq={seq}" + ("" if reply else "  (no reply)"))
                seq += 1
                next_stats = now + args.interval

            if args.rgb == "off":
                time.sleep(min(0.05, args.interval))
                continue

            # live colour update via `preset` (does not restart the video)
            if args.rgb_mode == "thermal":
                if args.demo_temp is not None:
                    # sweep 20->100C over 40s so every band is visible
                    temp = args.demo_temp if args.demo_temp >= 0 else \
                        20 + ((now - started) * 2) % 80
                else:
                    src = (last_stats or {}).get(args.rgb_source, {})
                    temp = float(src.get("temperature") or 0)
                phase = int(now - started) % 2 == 1   # flips every 1 s (0.5 Hz)
                cycled = proto.thermal_hex(temp, phase)
                value_col = cycled
            else:
                hue = ((now - started) * args.rgb_speed) % 1.0
                cycled = proto.hsv_hex(hue)
                value_col = proto.hsv_hex(hue + 0.5)

            title = cycled if args.rgb in ("title", "both") else args.title_color
            value = cycled if args.rgb in ("value", "both") else args.content_color
            if args.rgb == "both":
                value = value_col
            txn(h, proto.POST, proto.RES_PRESET,
                proto.preset_payload(slots, title_color=title,
                                     content_color=value, opacity=args.opacity),
                seq, timeout=0.0)
            seq += 1
            time.sleep(1.0 / max(args.rgb_fps, 0.5))
    except KeyboardInterrupt:
        print("\nsending disconn...")
    finally:
        try:
            txn(h, proto.POST, proto.RES_DISCONN, None, seq)
        except Exception:
            pass
        h.close()


if __name__ == "__main__":
    main()
