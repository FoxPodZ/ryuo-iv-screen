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
    (close ASUS Info Hub first — it talks to the cooler too)

    python ryuo_ctl.py get config
    python ryuo_ctl.py get all
    python ryuo_ctl.py get spec
    python ryuo_ctl.py brightness 30
    python ryuo_ctl.py items "CPU Temperature" "CPU Load" "Date&Time"
    python ryuo_ctl.py raw POST temperature "{\"value\":\"Celsius\"}"

    python ryuo_ctl.py info                  # POST conn: firmware, attributes, media
    python ryuo_ctl.py ls                    # just the media listing
    python ryuo_ctl.py rm clip.mp4 [more.png ...]
    python ryuo_ctl.py rm --except keep.mp4  # delete every other file in pcMedia/

    python ryuo_ctl.py --list
    python ryuo_ctl.py --index 1 get config

info, ls and rm are confirmed on fw 1.0.10; rm --except is read from source
only. There is no upload: the firmware has no working upload over HID, so
media goes on with `adb push` to /sdcard/pcMedia/.
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import quote

import ryuo_hid
import ryuo_proto as proto
from ryuo_screen.client import (
    API_PREFIX, ApiError, ServiceUnavailable, UnixApiClient, add_service_options,
    direct_device, patch_state, print_state_result, slots_for_items,
)
from ryuo_screen.media import MediaCatalog
from ryuo_screen.ownership import OwnershipError

VID, PID = proto.VID, proto.PID


def open_dev(vid: int | None = None, pid: int = PID, index: int | None = None):
    import hid

    # vid=None means "any vendor id with this product id" -- see proto.VIDS.
    devs = proto.find_devices(hid, vid, pid)
    if not devs:
        ids = f"{vid:04X}:{pid:04X}" if vid else f"????:{pid:04X}"
        sys.exit(f"no HID device {ids} — is the cooler plugged in? "
                 f"(--list to see what enumerated)")

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
        timeout: float = 2.0, quiet: bool = False):
    """Send one request and return the decoded reply body, or None.

    quiet=True prints only the request line and leaves the reply to the caller
    -- for replies that carry something (a serial number) that shouldn't land
    in a pasted log unredacted.
    """
    frame = proto.request(method, resource, payload, seq=seq)
    ryuo_hid.write_frame(h, frame)
    # The frame always goes out as one 1024-byte report (PROTOCOL.md §2);
    # its unpadded size is the number worth seeing, since 1024 is the limit.
    size = len(frame.rstrip(b"\x00"))
    print(f"--> {method} {resource} ({size} of {proto.REPORT_SIZE} bytes)"
          + (f"  {json.dumps(payload)}" if payload else ""))

    # Run next to ryuo_send.py, this handle also receives every reply to
    # ryuo_send's own requests. read_reply() skips them by AckNumber; count
    # them rather than printing each one.
    skipped = []
    body = ryuo_hid.read_reply(h, seq, timeout, log=skipped.append)
    undecodable = [m for m in skipped
                   if m.startswith(ryuo_hid.SKIP_UNDECODABLE)]
    foreign = len(skipped) - len(undecodable)
    for m in undecodable:
        print(f"<-- {m}")
    if foreign:
        print(f"    (skipped {foreign} repl{'y' if foreign == 1 else 'ies'} to "
              f"other requests -- ryuo_send.py or Info Hub running?)")

    if body is None:
        print("<-- (no reply)")
        return None
    if quiet:
        return body
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


# ------------------------------------------------------------- media files

class DeviceError(RuntimeError):
    pass


def conn(h, seq: int = 1) -> dict:
    """POST conn -> the device's capability descriptor, including its serial."""
    body = txn(h, proto.POST, proto.RES_CONN, None, seq=seq, quiet=True)
    info = proto.reply_json(body)
    if not isinstance(info, dict):
        raise DeviceError("no descriptor in the conn reply: "
                          + (body.split("\r\n")[0] if body else "no reply at all"))
    return info


def _print_media(custom, preset) -> None:
    for kind, names in (("custom", custom), ("preset", preset)):
        print(f"{kind} ({len(names)}):")
        for name in names:
            print(f"  {name}")


def _service_path(cmd, rest):
    if cmd in ("brightness", "items") or (cmd == "get" and (not rest or rest[0] == "config")):
        return "/state"
    if cmd == "info" and "--serial" not in rest:
        return "/device"
    if cmd in ("ls", "rm"):
        return "/media"
    return None


def _run_service(client, cmd, rest, document) -> None:
    if cmd in ("get", "info"):
        print(json.dumps(document, indent=2))
    elif cmd == "brightness":
        result = patch_state(client, document, "/brightness", brightness=_brightness(rest))
        print_state_result(result)
    elif cmd == "items":
        slots = slots_for_items(proto.sysinfo_slots(*_items(rest)), client)
        print_state_result(patch_state(client, document, "/screen", slots=slots))
    else:
        try:
            catalog = MediaCatalog(factory=document.get("factory"),
                                   custom=document.get("custom"))
        except TypeError as exc:
            raise ApiError(f"Ryuo service returned an invalid media listing: {exc}") from exc
        if cmd == "ls":
            _print_media(catalog.custom, catalog.factory)
        else:
            _delete_service_media(client, catalog, _media_delete(rest))


def _delete_service_media(client, catalog, payload) -> None:
    if "exclude" in payload:
        names = [name for name in catalog.custom
                 if name not in payload["exclude"] and catalog.classify(name) == "custom"]
    else:
        names = payload["include"]
    for name in names:
        proto.check_media_name(name)
        if catalog.classify(name) != "custom":
            raise DeviceError(f"{name!r} is not listed as custom media")
    for name in dict.fromkeys(names):
        result = client.request("DELETE", API_PREFIX + "/media/" + quote(name, safe=""))
        print(json.dumps(result))
        if (result.get("error") or result.get("confirmed") is not True
                or result.get("applied") is not True):
            raise DeviceError(result.get("error") or f"deletion of {name!r} was not confirmed")


def _brightness(rest) -> int:
    if not rest:
        sys.exit("usage: brightness <value>   (0-102; the value is "
                 "scaled ~2.5x into a kernel backlight that clamps at "
                 "255, so 100 is only ~98% of max and 102 is full)")
    return int(rest[0])


def _items(rest):
    if not rest:
        sys.exit("usage: items <name> [name ...]   (up to 6)")
    return list(rest)


def _media_delete(rest):
    if not rest or rest == ["--except"]:
        sys.exit("usage: rm <name> [name ...]          delete these\n"
                 "       rm --except <name> [name ...] delete every "
                 "OTHER file in pcMedia/\n"
                 "  only ever touches /sdcard/pcMedia/, never the "
                 "presets")
    if rest[0] == "--except":
        return proto.media_delete_payload(exclude=rest[1:])
    return proto.media_delete_payload(include=list(rest))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="single-shot request/response tool for the Ryuo IV screen",
        epilog="commands: get <resource> | brightness <n> | rotate <deg> | "
               "items <a> <b> ... | info [--serial] | ls | "
               "rm <name> ... | rm --except <name> ... | "
               "raw <METHOD> <resource> [json]")
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=None,
                    help="pin a vendor id; default accepts any (it changes "
                         "between firmware versions)")
    ap.add_argument("--pid", type=lambda x: int(x, 0))
    ap.add_argument("--index", type=int, default=None,
                    help="which enumerated interface to open (see --list)")
    ap.add_argument("--list", action="store_true",
                    help="list enumerated interfaces and exit")
    add_service_options(ap)
    ap.add_argument("argv", nargs=argparse.REMAINDER,
                    help="command and its arguments")
    args = ap.parse_args()
    pid = PID if args.pid is None else args.pid

    if args.list:
        import hid

        found = proto.find_devices(hid, args.vid, pid)
        if not found:
            ids = (f"{args.vid:04X}:{pid:04X}" if args.vid
                   else f"any vendor with product {pid:04X}")
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

    path = _service_path(cmd, rest)
    try:
        if path is not None and not args.direct and all(
            value is None for value in (args.vid, args.pid, args.index)
        ):
            client = UnixApiClient(args.socket)
            try:
                document = client.request("GET", API_PREFIX + path)
            except ServiceUnavailable:
                pass
            else:
                _run_service(client, cmd, rest, document)
                return
        with direct_device(args.socket, open_dev, args.vid, pid, args.index) as h:
            _run_direct(h, cmd, rest)
    except (ApiError, DeviceError, OwnershipError, ValueError) as ex:
        sys.exit(f"error: {ex}")


def _run_direct(h, cmd, rest) -> None:
    if cmd == "get":
        txn(h, proto.GET, rest[0] if rest else "config")
    elif cmd == "brightness":
        txn(h, proto.POST, proto.RES_BRIGHTNESS, {"value": _brightness(rest)})
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
        txn(h, proto.POST, proto.RES_SYSINFO_DISPLAY, {"items": _items(rest)})
    elif cmd in ("info", "ls"):
        info = conn(h)
        if cmd == "ls":
            media = info.get("media") or {}
            _print_media(media.get("custom") or [], media.get("preset") or [])
        else:
            # The reply carries the unit's serial number. Output from
            # this tool ends up pasted into issues, so it stays blank
            # unless asked for.
            print(json.dumps(info if "--serial" in rest
                             else proto.redact_conn(info), indent=2))
    elif cmd == "rm":
        txn(h, proto.POST, proto.RES_MEDIA_DELETE, _media_delete(rest))
    elif cmd == "raw":
        if len(rest) < 2:
            sys.exit('usage: raw <METHOD> <resource> [json]\n'
                     '  e.g. raw POST temperature \'{"value":"Celsius"}\'')
        method, resource = rest[0], rest[1]
        if resource == proto.RES_UPGRADE:
            sys.exit("refusing to send `upgrade`: it starts an update in "
                     "RKUpdateService, and nothing in this repo goes near "
                     "the OTA path (PROTOCOL.md §11). If you really need "
                     "it, edit this file -- it's one line.")
        payload = json.loads(rest[2]) if len(rest) > 2 else None
        if (resource == proto.RES_TRANSPORT and isinstance(payload, dict)
                and payload.get("type") == "firmware"):
            sys.exit('refusing `transport` with type "firmware": the '
                     "matching `transported` asks RKUpdateService to look "
                     "for an update package. Same reason as `upgrade`.")
        txn(h, method, resource, payload)
    else:
        sys.exit(f"unknown command {cmd!r} — try: get, brightness, "
                 f"rotate, items, info, ls, rm, raw")


if __name__ == "__main__":
    main()
