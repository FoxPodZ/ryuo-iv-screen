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
ryuo_ctl.py — send single commands to the Ryuo IV screen and PRINT THE REPLY.

    pip install -r requirements.txt
    (close ASUS Info Hub first — it holds the HID handle)

    python ryuo_ctl.py get config
    python ryuo_ctl.py get all
    python ryuo_ctl.py get spec
    python ryuo_ctl.py brightness 30
    python ryuo_ctl.py items "CPU Temperature" "CPU Load" "Date&Time"
    python ryuo_ctl.py raw POST temperature "{\"value\":\"Celsius\"}"

    python ryuo_ctl.py --list
    python ryuo_ctl.py --index 1 get config
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import hid
import ryuo_proto as proto

VID, PID = proto.VID, proto.PID


def open_dev(vid: int | None = None, pid: int = PID, index: int | None = None):
    # vid=None means "any vendor id with this product id" -- see proto.VIDS.
    devs = proto.find_devices(hid, vid, pid)
    if not devs:
        ids = f"{vid:04X}:{pid:04X}" if vid else f"????:{pid:04X}"
        sys.exit(f"no HID device {ids} — cooler unplugged, "
                 f"or Info Hub still running? (--list to see what enumerated)")

    if index is not None:
        if not 0 <= index < len(devs):
            sys.exit(f"--index {index} out of range: {len(devs)} interface(s) "
                     f"enumerated, use --list to see them")
        pick = devs[index]
    else:
        pick = next((d for d in devs
                     if d.get("interface_number") == proto.INTERFACE), devs[0])

    h = hid.device()
    try:
        h.open_path(pick["path"])
    except OSError as ex:
        sys.exit(f"could not open {pick['path']!r}: {ex}\n"
                 f"permission problem? install 70-ryuo.rules, or run as root.")
    h.set_nonblocking(1)
    return h


def txn(h, method: str, resource: str, payload=None, seq: int = 1,
        timeout: float = 2.0):
    frame = proto.request(method, resource, payload, seq=seq)

    # same chunking as ryuo_send.py: one 1024-byte report at a time.
    written = 0
    for off in range(0, len(frame), proto.REPORT_SIZE):
        chunk = frame[off:off + proto.REPORT_SIZE].ljust(proto.REPORT_SIZE, b"\x00")
        n = h.write(b"\x00" + chunk)
        if n < 0:
            raise OSError("HID write failed")
        written += n
    print(f"--> {method} {resource} ({written} bytes, "
          f"{len(frame) // proto.REPORT_SIZE} report(s))"
          + (f"  {json.dumps(payload)}" if payload else ""))

    buf = bytearray()
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = h.read(proto.REPORT_SIZE)
        if data:
            buf += bytes(data)
            if buf.count(proto.START) >= 2:
                s = buf.index(proto.START)
                e = buf.index(proto.END, s + 1)
                raw = bytes(buf[s:e + 1])
                try:
                    body = proto.decode(raw).decode(errors="replace")
                except Exception as ex:
                    print(f"<-- undecodable ({ex}): {raw[:48].hex(' ').upper()}")
                    return None
                head, _, content = body.partition("\r\n\r\n")
                print("<--", head.replace("\r\n", " | "))
                if content.strip():
                    try:
                        print(json.dumps(json.loads(content), indent=2)[:4000])
                    except Exception:
                        print(content[:4000])
                else:
                    print("    (empty body)")
                return body
        else:
            time.sleep(0.02)
    print("<-- (no reply)")
    return None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="single-shot request/response tool for the Ryuo IV screen",
        epilog="commands: get <resource> | brightness <n> | rotate <deg> | "
               "items <a> <b> ... | "
               "raw <METHOD> <resource> [json]")
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=None,
                    help="pin a vendor id; default accepts any (it changes "
                         "between firmware versions)")
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=PID)
    ap.add_argument("--index", type=int, default=None,
                    help="which enumerated interface to open (see --list)")
    ap.add_argument("--list", action="store_true",
                    help="list enumerated interfaces and exit")
    ap.add_argument("argv", nargs=argparse.REMAINDER,
                    help="command and its arguments")
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

    if not args.argv:
        ap.print_help()
        sys.exit(1)
    cmd, rest = args.argv[0], args.argv[1:]

    h = open_dev(args.vid, args.pid, args.index)
    try:
        if cmd == "get":
            txn(h, proto.GET, rest[0] if rest else "config")
        elif cmd == "brightness":
            if not rest:
                sys.exit("usage: brightness <value>   (0-102; the value is "
                         "scaled ~2.5x into a kernel backlight that clamps at "
                         "255, so 100 is only ~98% of max and 102 is full)")
            txn(h, proto.POST, proto.RES_BRIGHTNESS, {"value": int(rest[0])})
        elif cmd == "rotate":
            if not rest:
                sys.exit("usage: rotate <degrees>   (0, 90, 180, 270)\n"
                         "  NOTE: dead resource. Writes a system property that\n"
                         "  nothing reads; the panel does not rotate. Kept for\n"
                         "  re-testing on future firmware.")
            txn(h, proto.POST, proto.RES_ROTATE, {"degree": int(rest[0])})
            print("\nNOTE: THIS DOES NOT ROTATE ANYTHING. It sets")
            print("persist.vendor.orientation and nothing else. The property")
            print("is written and survives a reboot -- confirmed on fw 1.0.10 --")
            print("but nothing on the device reads it and the panel never turns.")
            print("Orientation comes from the read-only build property")
            print("ro.surface_flinger.primary_display_orientation, which cannot")
            print("be changed at runtime. The command is kept only so the result")
            print("can be re-checked on future firmware.")
        elif cmd == "items":
            if not rest:
                sys.exit("usage: items <name> [name ...]   (up to 6)")
            txn(h, proto.POST, proto.RES_SYSINFO_DISPLAY, {"items": list(rest)})
        elif cmd == "raw":
            if len(rest) < 2:
                sys.exit('usage: raw <METHOD> <resource> [json]\n'
                         '  e.g. raw POST temperature \'{"value":"Celsius"}\'')
            method, resource = rest[0], rest[1]
            if resource == proto.RES_UPGRADE:
                sys.exit("refusing to send `upgrade`: it hands a package to "
                         "RKUpdateService, and nothing in this repo goes near "
                         "the OTA path (PROTOCOL.md §11). If you really need "
                         "it, edit this file -- it's one line.")
            payload = json.loads(rest[2]) if len(rest) > 2 else None
            txn(h, method, resource, payload)
        else:
            sys.exit(f"unknown command {cmd!r} — "
                     f"try: get, brightness, rotate, items, raw")
    finally:
        h.close()


if __name__ == "__main__":
    main()
