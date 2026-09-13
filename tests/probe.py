#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 FoxPodZ (foxpodz.de)  <https://github.com/foxpodz/ryuo-iv-screen>
"""
probe.py — work through the unknowns in PROTOCOL.md, one at a time, on real
hardware, and write down what actually happened.

    python tests/probe.py                 # run everything
    python tests/probe.py --only brightness_scale
    python tests/probe.py --list

Every probe sends one request, shows you the reply, then asks what the screen
did. Answers go to tests/probe-results.md, which you can paste into an issue or
straight into PROTOCOL.md. Nothing here decides anything for you — you are the
instrument, this just holds the clipboard.

Where a question can be answered by reading a number instead of by looking, it
is. The brightness probes read /sys/class/backlight over adb, because two
separate runs of an eyeball-based version disagreed with each other while the
kernel knew the answer the whole time.

SAFETY
  * `upgrade` is not in here and will not be added. It hands a zip to
    RKUpdateService. Nothing about that belongs in a probe script.
  * Every probe re-pushes a known-good config afterwards, WITH media playing,
    so a bad value can't leave you judging the next probe against a black
    screen.
  * Ctrl-C at any point sends `disconn` and exits cleanly.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import subprocess
import sys
import threading
import time

import hid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ryuo_proto as proto

RESULTS = os.path.join(os.path.dirname(__file__), "probe-results.md")


# ----------------------------------------------------------------- plumbing

class Link:
    """Transport, plus the keepalive that everything here depends on.

    PROTOCOL.md §12 step 6: loop POST all every second, forever, or the screen
    goes back to stock. Earlier versions of this harness sent a few telemetry
    frames and then blocked on input() while the operator read the panel and
    typed an answer -- by which point the session had lapsed and the screen had
    dropped to standby: widgets gone, panel dimmed, standby.mp4 playing.

    The symptom was maddening: run the probe with Info Hub open in the
    background and everything worked, because Info Hub was supplying the
    keepalive. Close it and every change reverted after one refresh. Several
    earlier probe runs are contaminated by this.
    """

    def __init__(self, vid, pid, index=None, media="RYUO_IV_HW_Info_02.mp4"):
        self.media = media
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._tick = 0
        devs = proto.find_devices(hid, vid, pid)
        if not devs:
            ids = f"{vid:04X}:{pid:04X}" if vid else f"????:{pid:04X}"
            sys.exit(f"no HID device {ids} — cooler unplugged, "
                     f"or Info Hub still running?")
        pick = (devs[index] if index is not None else
                next((d for d in devs
                      if d.get("interface_number") == proto.INTERFACE), devs[0]))
        self.h = hid.device()
        self.h.open_path(pick["path"])
        self.h.set_nonblocking(1)
        self.seq = 1

    def send(self, method, resource, payload=None, timeout=1.5):
        with self._lock:
            return self._send_locked(method, resource, payload, timeout)

    def _send_locked(self, method, resource, payload=None, timeout=1.5):
        frame = proto.request(method, resource, payload, seq=self.seq)
        self.seq += 1
        for off in range(0, len(frame), proto.REPORT_SIZE):
            chunk = frame[off:off + proto.REPORT_SIZE].ljust(proto.REPORT_SIZE, b"\x00")
            if self.h.write(b"\x00" + chunk) < 0:
                return "<write failed>"
        buf, deadline = bytearray(), time.time() + timeout
        while time.time() < deadline:
            data = self.h.read(proto.REPORT_SIZE)
            if data:
                buf += bytes(data)
                if buf.count(proto.START) >= 2:
                    s = buf.index(proto.START)
                    e = buf.index(proto.END, s + 1)
                    try:
                        return proto.decode(bytes(buf[s:e + 1])).decode(errors="replace")
                    except Exception as ex:
                        return f"<undecodable: {ex}>"
            else:
                time.sleep(0.02)
        return None

    def known_good(self):
        """Put the screen back somewhere sane — WITH media playing.

        This matters more than it looks. Without a media file the panel is
        black, and every probe that asks "did anything change on screen?" gets
        answered against a black rectangle. RYUO_IV_HW_Info_02.mp4 ships on
        every unit in /sdcard/pcMediaPreset/, so this needs nothing pushed.
        """
        self.send(proto.POST, proto.RES_CONFIG, proto.config_payload(
            brightness=85,
            config=proto.screen_config(
                media=[self.media],
                play_mode=proto.PLAY_SINGLE,
                sysinfo=proto.sysinfo_slots("CPU Temperature", "GPU Temperature",
                                            "Date&Time"))))
        time.sleep(1.6)

    def start_keepalive(self, interval=1.0):
        """Pump POST all in the background so the session never lapses."""
        if self._thread:
            return
        self._stop.clear()

        def loop():
            while not self._stop.wait(interval):
                try:
                    self.telemetry()
                except Exception:
                    pass          # a dropped frame is not worth killing this

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop_keepalive(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def telemetry(self, fans=True):
        """One POST all, so widgets have values to render.

        Fan widgets appear to need a matching fans[].name in the telemetry
        before they will draw anything, so a config-only probe can report a
        false negative for them.
        """
        # Values SWEEP rather than sit still. A slot with no matching telemetry
        # keeps its previous number and looks identical to a working one, so
        # the only way to tell a live readout from a fossil is to watch it
        # move. Everything here changes every tick.
        self._tick += 1
        n = self._tick % 20
        self.send(proto.POST, proto.RES_ALL, proto.pc_info(
            cpu={"load": 20 + n, "temperature": 40 + n,
                 "temperaturePackage": 45 + n, "speedAverage": 4000 + n * 10,
                 "power": 50 + n, "voltage": 1.0 + n / 100, "usage": 30 + n},
            gpu={"hasDedicated": True, "load": 25 + n, "temperature": 50 + n,
                 "fan": 1000 + n * 10, "speed": 2000 + n * 10,
                 "power": 80 + n, "voltage": 0.9 + n / 100},
            memory={"total": 32768, "used": 16384, "load": 40 + n,
                    "temperature": 0, "speed": 3000 + n},
            disk={"total": 1000, "used": 400, "load": 10 + n, "activity": 0,
                  "temperature": 30 + n, "readSpeed": 0, "writeSpeed": 0},
            motherboard={"temperature": 30 + n, "chipsetTemperature": 45 + n},
            # Shape copied from the canned PcInfo in MainActivity's own test
            # harness, which carries a "type" field Info Hub never sends and a
            # longer name format ("Fan CPUFANIN0"). Neither turned out to
            # matter (the Fan * strings simply weren't real items -- see §10),
            # but both forms are kept so the harness exercises them.
            fans=[{"onBoard": True, "type": "Fan", "name": "CPU", "value": 1500},
                  {"onBoard": True, "type": "Fan", "name": "Fan CPUFANIN0", "value": 1500},
                  {"onBoard": True, "type": "Fan", "name": "AIO Pump", "value": 3200},
                  {"onBoard": True, "type": "Fan", "name": "Fan AIO Pump", "value": 3200},
                  {"onBoard": True, "type": "Fan", "name": "Chassis4", "value": 500 + n},
                  {"onBoard": True, "type": "Fan", "name": "Chassis 5", "value": 540 + n}]
            if fans else []))

    def close(self):
        self.stop_keepalive()
        try:
            self.send(proto.POST, proto.RES_DISCONN, None, timeout=0.3)
        except Exception:
            pass
        self.h.close()


def ask(question, options=("y", "n", "skip")):
    opts = "/".join(options)
    while True:
        a = input(f"  ?? {question} [{opts}] > ").strip().lower()
        if a in options:
            return a
        if a == "" and options:
            return options[0]


def note(question):
    return input(f"  ?? {question}\n     > ").strip()


def settle(link, what="the new media"):
    """Wait until the panel has ACTUALLY caught up before asking anything.

    Media load latency on this device is longer than any fixed sleep that is
    also tolerable to sit through. A whole probe run was contaminated by this:
    the tester realised several answers in that the picture had only just
    appeared, so the earlier "yes" answers were describing the previous state.
    A fixed timeout cannot fix that. Asking can.
    """
    while True:
        a = ask(f"is {what} actually on screen yet?", ("y", "wait", "skip"))
        if a != "wait":
            return a
        time.sleep(3)


def _backlight_sysfs():
    """Read the kernel backlight value over adb. Returns (path, reader) or None.

    Eyes are a terrible instrument for this — two runs of an earlier version of
    the brightness probe disagreed about whether 255 was brighter than 100,
    which is exactly what expectation bias looks like on a 2% difference.
    """
    try:
        r = subprocess.run(["adb", "shell", "ls /sys/class/backlight/"],
                           capture_output=True, text=True, timeout=8)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    names = [n.strip() for n in r.stdout.split() if n.strip()]
    if not names:
        return None
    path = f"/sys/class/backlight/{names[0]}/brightness"

    def read():
        try:
            q = subprocess.run(["adb", "shell", f"cat {path}"],
                               capture_output=True, text=True, timeout=8)
            return q.stdout.strip()
        except Exception as ex:
            return f"<{ex}>"
    return path, read


# ------------------------------------------------------------------- probes

PROBES = []


def probe(key, section, title):
    def deco(fn):
        PROBES.append((key, section, title, fn))
        return fn
    return deco


@probe("brightness_scale", "§4", "Map the API brightness value onto the kernel backlight")
def _brightness(link):
    out = {}
    sysfs = _backlight_sysfs()
    if sysfs:
        path, read = sysfs
        print(f"  reading {path} over adb — no eyeballing needed")
        out["sysfs_path"] = path
    else:
        print("  !! adb not available, or no /sys/class/backlight entry.")
        print("  !! Falling back to your eyes, which is what got this wrong")
        print("  !! the first two times. adb is strongly preferred here.")

    for value in (0, 10, 25, 50, 75, 85, 100, 125, 150, 200, 255):
        link.send(proto.POST, proto.RES_BRIGHTNESS, {"value": value})
        time.sleep(1.2)
        if sysfs:
            kern = read()
            dcs = f"  (DCS ~{int(kern) * 13})" if kern.isdigit() else ""
            print(f"  API {value:3} -> kernel backlight {kern}{dcs}")
            out[f"api_{value}"] = kern
        else:
            out[f"api_{value}"] = note(f"API {value}: how bright?")

    if sysfs:
        top = [out.get(f"api_{v}") for v in (125, 150, 200, 255)]
        at100 = out.get("api_100")
        if len(set(top)) == 1 and top[0] is not None:
            if at100 == top[0]:
                print(f"\n  => 100 and everything above it give kernel {top[0]}. "
                      f"Saturates at or below 100.")
                out["verdict"] = f"saturates at <=100 (kernel {top[0]})"
            else:
                print(f"\n  => 100 gives kernel {at100}, but >=125 gives {top[0]}. "
                      f"So 100 is NOT maximum — the API is scaled and the KERNEL "
                      f"clamps, not the app.")
                print(f"  => expected saturation point: API "
                      f"{round(int(top[0]) / 2.5)} if the factor is 2.5")
                out["verdict"] = (f"100 -> {at100}, >=125 -> {top[0]}; "
                                  f"kernel-side clamp, 100 is not full")
        else:
            out["verdict"] = f"no plateau found: {top}"
    else:
        out["verdict"] = note("did anything above 100 look different?")

    link.send(proto.POST, proto.RES_BRIGHTNESS, {"value": 85})
    return out


@probe("brightness_precision", "§4", "Falsify the two-denominator rounding model")
def _brightness_precision(link):
    """The model is floor(api*2.5) -> i/255 -> round(1 + f*254).

    It reproduces every point measured so far, but it is FITTED, not read from
    source. The inputs below were never tested and the model commits to an
    exact answer for each. One disagreement kills it.
    """
    def predict(v):
        if v == 0:
            return 0
        i = min(math.floor(v * 2.5), 255)
        return min(round(1 + (i / 255.0) * 254), 255)

    sysfs = _backlight_sysfs()
    if not sysfs:
        return {"skipped": "needs adb + /sys/class/backlight to mean anything"}
    path, read = sysfs

    out = {"model": "floor(api*2.5) -> i/255 -> round(1+f*254)"}
    agree = disagree = 0
    # low end: where the +1 offset should show most clearly.
    # 95-103: the saturation knee. 101 vs 102 is the whole "100 isn't max".
    for v in (1, 2, 3, 4, 5, 95, 96, 97, 98, 99, 100, 101, 102, 103):
        link.send(proto.POST, proto.RES_BRIGHTNESS, {"value": v})
        time.sleep(1.0)
        got, want = read(), predict(v)
        ok = got.isdigit() and int(got) == want
        agree, disagree = agree + ok, disagree + (not ok)
        print(f"  API {v:3} -> kernel {got:>4}   predicted {want:>4}   "
              f"{'ok' if ok else 'MISMATCH'}")
        out[f"api_{v}"] = f"{got} (predicted {want})"

    print(f"\n  {agree} agree, {disagree} disagree")
    if disagree == 0:
        print("  => model survives, now predicting 21 points rather than 7.")
        out["verdict"] = "model holds across all tested values"
    else:
        print("  => model is WRONG. Good — that's a real result, write it down.")
        out["verdict"] = f"model falsified on {disagree} value(s)"

    link.send(proto.POST, proto.RES_BRIGHTNESS, {"value": 85})
    return out


@probe("waterblockscreen", "§4", "Does waterBlockScreen {'enable': bool} turn the panel off?")
def _wbs(link):
    out = {}
    print("  -> POST waterBlockScreen {'enable': false}")
    out["reply_off"] = link.send(proto.POST, proto.RES_WATERBLOCK_SCREEN, {"enable": False})
    time.sleep(2)
    out["went_dark"] = ask("did the screen go dark / off?")
    print("  -> POST waterBlockScreen {'enable': true}")
    out["reply_on"] = link.send(proto.POST, proto.RES_WATERBLOCK_SCREEN, {"enable": True})
    time.sleep(2)
    out["came_back"] = ask("did it come back on?")
    if out["came_back"] == "n":
        print("  !! if it's stuck off: adb reboot clears the held config.")
    return out


@probe("display_in_sleep", "§4", "Which displayInSleep value triggers the screensaver?")
def _dis(link):
    """The last run switched the panel to Screensaver.mp4, but both values were
    sent before the question was asked, so which one did it is still open."""
    out = {}
    for v in (False, True):
        print(f"  -> POST displayInSleep {{'enable': {v}}}")
        out[f"reply_{v}"] = link.send(proto.POST, proto.RES_DISPLAY_IN_SLEEP,
                                      {"enable": v})
        time.sleep(3)
        out[f"observed_{v}"] = ask(f"with enable={v}: did the panel switch to a "
                                   f"screensaver clip?")
        if out[f"observed_{v}"] == "y":
            out[f"desc_{v}"] = note("which clip, if you can tell?")
        link.known_good()
    return out


@probe("rotate", "§4", "DEAD — property is written and persists, panel never turns")
def _rotate(link):
    """Handler is getInt("degree") -> setProperty(persist.vendor.orientation).

    CONFIRMED DEAD on fw 1.0.10: the property is written, survives a reboot and
    reads back correctly, and the panel never turns. Nothing consumes it.
    Orientation comes from the read-only ro.surface_flinger.* build property.
    Kept so the result can be re-checked on future firmware.
    """
    def getprop():
        try:
            r = subprocess.run(
                ["adb", "shell", "getprop persist.vendor.orientation"],
                capture_output=True, text=True, timeout=8)
            return r.stdout.strip() or "(unset)"
        except Exception as ex:
            return f"<{ex}>"

    def setprop(value):
        try:
            subprocess.run(
                ["adb", "shell", f"setprop persist.vendor.orientation {value}"],
                capture_output=True, text=True, timeout=8)
        except Exception:
            pass

    out = {"before": getprop()}
    print(f"  persist.vendor.orientation = {out['before']!r}  (will be put back)")

    for deg in (90, 0, 180):        # NOTE: ends at 180, deliberately
        print(f"  -> POST rotate {{'degree': {deg}}}")
        reply = link.send(proto.POST, proto.RES_ROTATE, {"degree": deg})
        time.sleep(1.2)
        got = getprop()
        print(f"     prop is now {got!r}  {'ok' if got == str(deg) else 'MISMATCH'}")
        out[f"degree_{deg}"] = got
        out[f"reply_{deg}"] = (reply or "(no reply)").splitlines()[0]

    # wrong-key control: demonstrates the silent-failure path
    print("  -> POST rotate {'value': 270}   (wrong key — should be ignored)")
    link.send(proto.POST, proto.RES_ROTATE, {"value": 270})
    time.sleep(1.2)
    out["wrong_key_prop"] = getprop()
    print(f"     prop is still {out['wrong_key_prop']!r} — getInt throws into")
    print("     the catch block, so a wrong key ACKs 200 and does nothing")

    # An earlier version of this probe swept 180 -> 90 -> 0 and THEN asked the
    # operator to reboot and look. The property was 0, so of course the panel
    # came up unrotated. The order above ends at 180 so the reboot test is
    # actually testing something.
    print()
    print(f"  persist.vendor.orientation is now {getprop()!r}.")
    print("  KNOWN RESULT (fw 1.0.10): the property sticks across a reboot and")
    print("  the panel does NOT turn. Nothing on the device reads it. This")
    print("  probe is kept to re-check that on future firmware.")
    out["reboot_test"] = note("reboot now and say whether the panel came up "
                              "flipped (enter to skip)")
    if out["reboot_test"]:
        out["prop_after_reboot"] = getprop()

    # Put it back the way it was found. Nothing reads it, but it's a persist.
    # property on somebody else's cooler and leaving it at 180 is still rude.
    # If the original value couldn't be read (unset, or no adb), 0 is the
    # stock orientation.
    restore = out["before"] if out["before"].isdigit() else "0"
    setprop(restore)
    out["restored_to"] = getprop()
    print(f"  persist.vendor.orientation put back to {out['restored_to']!r}")
    return out


@probe("waterfall_mode", "§4", "DEAD — handler logs and returns, nothing wired to it")
def _waterfall(link):
    print("  `waterfallMode` parses {'enable': bool} and dispatches correctly,")
    print("  and then case 116 logs MSG_WATERFALLMODE_CHANGE and returns.")
    print("  That is the entire implementation. There is nothing to find.")
    print("  Kept only so nobody re-opens it as an unknown.")
    return {"status": "dead code, confirmed in source (case 116 logs and returns)"}


@probe("power_events", "§4", "`shutdown` dims the panel -- which event, if any, restores it?")
def _power(link):
    """`shutdown` dims the panel. That part is settled (fw 1.0.7).

    What is NOT settled is what brings it back. The run that found the dim
    credited one of the other events, but every probe was followed by
    known_good() -- a full config push, and config carries brightness -- so the
    restore could have been the event or the config. This version dims the
    panel, then tries each candidate event with NO config push in between, and
    only re-pushes the config once every candidate has had its turn.
    doPower only switches on a string, so nothing here flashes anything.
    """
    out = {}
    print("  -> POST power {'event': 'shutdown'}   (should dim the panel)")
    reply = link.send(proto.POST, proto.RES_POWER, {"event": "shutdown"})
    out["shutdown"] = (reply or "(no reply)").splitlines()[0]
    time.sleep(2)
    out["shutdown_dimmed"] = ask("did the panel dim?")

    print("  now each candidate, one at a time, with NO config push between them.")
    print("  the keepalive is running, but POST all carries no brightness, so")
    print("  anything that brings it back is the event itself.")
    for ev in ("standby", "resume", "wake", "sleep", "screen_on", "screen_off",
               "on", "off", "suspend"):
        print(f"  -> POST power {{'event': '{ev}'}}")
        reply = link.send(proto.POST, proto.RES_POWER, {"event": ev})
        out[ev] = (reply or "(no reply)").splitlines()[0]
        time.sleep(2)
        a = ask(f"is the panel back to full brightness after '{ev}'?")
        out[f"{ev}_restored"] = a
        if a == "y":
            out["restored_by"] = ev
            break
    else:
        out["restored_by"] = "none of the events tried"
    out["other_effects"] = note("anything else you saw along the way? "
                                "(enter for nothing)")

    link.known_good()
    out["config_restored"] = ask("and after the config push -- back to normal?")
    return out


@probe("fan_lcd", "§4", "Does fanLCD / fanLCDSet control anything?")
def _fanlcd(link):
    out = {}
    print("  Hard to judge by ear over case fans. If you can, watch")
    print("  `adb logcat` for a fan-related line instead of listening.")
    for res, payload in ((proto.RES_FAN_LCD, {"speed": "", "mode": ""}),
                         (proto.RES_FAN_LCD, {"speed": "50", "mode": "manual"}),
                         (proto.RES_FAN_LCD, {"speed": "100", "mode": "manual"}),
                         (proto.RES_FAN_LCD_SET, {"speed": "50", "mode": "manual"})):
        key = f"{res}:{json.dumps(payload)}"
        print(f"  -> POST {key}")
        reply = link.send(proto.POST, res, payload)
        out[key] = (reply or "(no reply)").splitlines()[0]
        time.sleep(2)
    out["observed"] = note("anything audible, visible, or in logcat?")
    return out


@probe("filter_value", "§9", "Is filter.value a real enum, or does ANY value trigger one effect?")
def _filter(link):
    """rain / vapor / Rain / Vapor all produced an overlay on the first run.

    Four out of four firing is suspicious: either the comparison is
    case-insensitive over a real enum, or the code only checks `!= null` and
    there is one effect with no selection at all. The nonsense values below are
    the control that tells those apart. If "banana" draws rain, the enum theory
    is dead.
    """
    out = {}
    print("  Overlays were only clearly visible over STILL images last time.")
    slots = proto.sysinfo_slots("CPU Temperature", "GPU Temperature", "Date&Time")
    still = note("filename of a still image in /sdcard/pcMedia/ "
                 "(enter to use the default clip instead)") or link.media

    for val in ("rain", "vapor", "Rain", "VAPOR", "banana", "xyzzy", "", None):
        cfg = proto.screen_config(media=[still], sysinfo=slots)
        cfg["settings"]["filter"]["value"] = val
        print(f"  -> POST config  filter.value = {val!r}")
        link.send(proto.POST, proto.RES_CONFIG, proto.config_payload(config=cfg))
        time.sleep(2.5)
        if settle(link, f"the image (filter.value={val!r})") == "skip":
            out[str(val)] = "skip"
            continue
        got = ask(f"overlay visible with filter.value={val!r}?")
        out[str(val)] = got
        if got == "y":
            out[f"{val}_desc"] = note("same as the previous one, or different?")
    out["verdict"] = note("did the nonsense values ('banana', 'xyzzy') also draw "
                          "an overlay? y => it's just a null check, not an enum")
    link.known_good()
    return out


@probe("badges", "§9", "DEAD — List<String> with no reader anywhere in the app")
def _badges(link):
    print("  `badges` is a List<String> on PmSetting with a getter, a setter")
    print("  and a toString(), and no reader anywhere. Same story for `align`,")
    print("  `position` and `color` — leftovers from an older schema.")
    print("  Only titleColor, contentColor and filter.opacity are live.")
    return {"status": "dead field, confirmed in source (no reader)"}


@probe("widget_strings", "§10", "Which widget item strings actually render?")
def _widgets(link):
    out = {}
    unconfirmed = [s for s in proto.SYSINFO_ITEMS
                   if s not in ("CPU Temperature", "GPU Temperature", "Date&Time")]
    print("  Item list now read from the renderer's subTitle map, so these")
    print("  should ALL work. The four Fan * strings are gone -- they never")
    print("  existed. Watch for the two known renderer bugs while you're here:")
    print("    GPU Power   -> unit wrongly reads C/F")
    print("    GPU Usage   -> identical number to GPU Load")
    print("  (CPU Voltage is fine -- it renders 'V'. The 'literal 2' scare was")
    print("   a decompiler artefact, see PROTOCOL.md section 10.)")
    print(f"  {len(unconfirmed)} unconfirmed strings, six at a time.")
    print("  Telemetry is pushed alongside each batch so the widgets have")
    print("  values to draw — Fan * widgets in particular may render nothing")
    print("  unless a matching fans[].name is present in POST all.")
    for i in range(0, len(unconfirmed), 6):
        batch = unconfirmed[i:i + 6]
        # POST sysinfoDisplay, NOT POST config. config is session setup; this
        # resource exists specifically to change widgets on a live session,
        # and run 2 of this probe changed nothing at all using the config path.
        print(f"  -> POST sysinfoDisplay {{'items': {batch}}}")
        link.send(proto.POST, proto.RES_SYSINFO_DISPLAY, {"items": list(batch)})
        time.sleep(2.5)             # keepalive is already pumping POST all
        changed = ask("did the widget row CHANGE from the previous six?",
                      ("y", "n", "skip"))
        out[f"batch_{i//6}_changed"] = changed
        if changed == "n":
            print("  !! Widgets didn't change. Every answer below would be about")
            print("  !! the OLD set, so they're being recorded as unknown.")
            for name in batch:
                out[name] = "unknown (row did not change)"
            continue

        for name in batch:
            out[name] = ask(f"did '{name}' render a label AND a value?",
                            ("both", "value-only", "label-only", "n", "skip"))
    link.known_good()
    return out


@probe("custom_readout", "§10", "Can you put arbitrary labelled numbers on the panel?")
def _custom_readout(link):
    """fan_item() says the item is "Fan Speed " + fans[].name, and the label
    drawn is info.substring(10). If that holds, any number with any label can
    go on the screen -- the single most useful thing in the protocol."""
    out = {}
    labels = ["Coolant", "NAS Bay 3", "Unread"]
    values = [3229, 41, 7]
    items = [proto.fan_item(l) for l in labels]
    print(f"  -> POST sysinfoDisplay {{'items': {items}}}")
    link.send(proto.POST, proto.RES_SYSINFO_DISPLAY, {"items": items})
    # the keepalive's fans[] don't carry these labels, so push our own for a
    # few ticks; interleaved with the keepalive, last writer wins per frame
    for _ in range(5):
        link.send(proto.POST, proto.RES_ALL, proto.pc_info(
            cpu={"load": 25, "temperature": 45},
            fans=[{"onBoard": True, "type": "Fan", "name": l, "value": v}
                  for l, v in zip(labels, values)]))
        time.sleep(0.6)
    for l, v in zip(labels, values):
        out[l] = ask(f"does the panel show '{l}' with the value {v}?")
    out["unit"] = note("what unit is shown next to them? (expect RPM)")
    out["verdict"] = note("if this works you can display ANY host metric under "
                          "ANY label -- confirm or deny")
    link.known_good()
    return out


@probe("renderer_bugs", "§10", "Confirm the two renderer bugs (and that voltage is fine)")
def _renderer_bugs(link):
    out = {}
    items = ["GPU Power", "GPU Load", "GPU Usage", "CPU Voltage",
             "Memory Utilization", "Hard Disk Temperature"]
    print("  Four of these have NO tile in Info Hub's picker at all:")
    print("    GPU Power, Memory Utilization, Memory Frequency,")
    print("    Hard Disk Temperature. If they render, they're yours for free.")
    print(f"  -> POST sysinfoDisplay {{'items': {items}}}")
    link.send(proto.POST, proto.RES_SYSINFO_DISPLAY, {"items": items})
    time.sleep(2.5)                 # keepalive supplies the sweeping values
    out["gpu_power_unit"] = note("GPU Power: what unit is printed? "
                                 "(bug says it wrongly shows C or F)")
    out["gpu_load_vs_usage"] = ask("are GPU Load and GPU Usage showing the "
                                   "SAME number?", ("y", "n", "skip"))
    # Voltage is fine -- confirmed rendering as e.g. "1.098V". The "literal 2"
    # theory came from a decompiler substituting the constant
    # ExifInterface.GPS_MEASUREMENT_INTERRUPTED, whose value is "V".
    out["cpu_voltage_unit"] = note("CPU Voltage: unit shown? (expect 'V')")
    out["disk_temp"] = ask("did 'Hard Disk Temperature' render? "
                           "(no tile for it in Info Hub)")
    out["mem_util"] = ask("did 'Memory Utilization' render? (no tile either)")
    out["gpu_power_rendered"] = ask("did 'GPU Power' render a value at all?")
    link.known_good()
    return out


@probe("screen_config_type_ratio", "§5", "What do ScreenConfig.Type and .ratio do?")
def _type_ratio(link):
    out = {}
    print("  Known so far: 1:1 and 4:3 visibly rescale a STILL; 2:1 shows no")
    print("  change (the panel is already ~2:1). Video is NOT black-screened by")
    print("  ratio -- an early run suggested that and it was media-load lag.")
    print("  This run separates the two media types properly.")
    still = note("filename of a still image in /sdcard/pcMedia/ "
                 "(enter to skip the stills half)")
    for media, kind in ((still, "still"), (link.media, "video")):
        if not media:
            continue
        for ratio in ("1:1", "2:1", "3:1", "4:3", "16:9", None):
            cfg = proto.screen_config(
                media=[media],
                sysinfo=proto.sysinfo_slots("CPU Temperature", "GPU Temperature"))
            cfg["ratio"] = ratio
            print(f"  -> POST config  ratio={ratio!r}  media={media!r} ({kind})")
            link.send(proto.POST, proto.RES_CONFIG,
                      proto.config_payload(config=cfg))
            time.sleep(2.5)
            if settle(link, f"the {kind} at ratio={ratio!r}") == "skip":
                out[f"{kind}_{ratio}"] = "skip"
                continue
            # absolute, not relative -- "nothing" in an earlier run meant
            # "looks like normal fullscreen", which is a description of the
            # state, not of a transition. Ask for the state.
            out[f"{kind}_{ratio}"] = ask(
                f"[{kind}] ratio={ratio!r}: how does it look NOW?",
                ("normal-fullscreen", "rescaled", "black", "skip"))
        out[f"{kind}_widgets"] = ask(
            f"[{kind}] did ALL the widgets still render, or only some?",
            ("all", "some", "skip"))
    link.known_good()
    return out


@probe("waterblock_screenid", "§4", "What does waterBlockScreenId do with a ScreenConfig?")
def _wbsid(link):
    """Never sent. Takes the same shape as `preset`, so the obvious question is
    whether it's a second display slot or just an alias for the same path."""
    out = {}
    cfg = proto.screen_config(
        media=[link.media],
        sysinfo=proto.sysinfo_slots("CPU Load", "GPU Load", "Date&Time"),
        title_color="#00FF9C")
    print("  -> POST waterBlockScreenId  {'config': <ScreenConfig, green labels>}")
    out["reply_wrapped"] = link.send(proto.POST, proto.RES_WATERBLOCK_SCREENID,
                                     {"config": cfg})
    time.sleep(2.5)
    out["applied_wrapped"] = ask("did the labels turn green / widgets change?")
    print("  -> POST waterBlockScreenId  <same config, unwrapped>")
    out["reply_flat"] = link.send(proto.POST, proto.RES_WATERBLOCK_SCREENID, cfg)
    time.sleep(2.5)
    out["applied_flat"] = ask("any change with the unwrapped shape?")
    link.known_good()
    return out


@probe("video_resolution", "§7", "SUPERSEDED — use tests/video_matrix.py instead")
def _video(link):
    print("  ** Superseded by tests/video_matrix.py, which holds each clip on")
    print("  ** screen with a live telemetry loop instead of letting the config")
    print("  ** revert after ~10s. Run that instead:")
    print("  **     python tests/video_matrix.py --encode source.mp4")
    print("  **     adb push out/*.mp4 /sdcard/pcMedia/")
    print("  **     python tests/video_matrix.py")
    return {"skipped": "use tests/video_matrix.py"}


@probe("zone_geometry", "§8", "Does the rendered split match the layout's 1606/634?")
def _zones(link):
    print("  MANUAL PROBE — the layout resource declares zone 2 = 634px hardcoded")
    print("  and zone 1 = layout_weight 1.0, so 2240 - 634 = 1606. That is a")
    print("  DECLARED width; this checks the RENDERED one.")
    print()
    print("    1. push two visually distinct images to /sdcard/pcMedia/")
    print("    2. python ryuo_send.py --media a.png --media2 b.png")
    print("    3. adb exec-out screencap -p > split.png")
    print("    4. open split.png, find the x where the two images meet")
    print()
    out = {}
    out["divider_x"] = note("pixel column where zone 1 ends (expect 1606, "
                            "NOT the 1600 Info Hub's crop tool implies)")
    out["image_size"] = note("full size of split.png (expect 2240x1080)")
    return out


# --------------------------------------------------------------------- runner

def write_results(results, meta):
    with open(RESULTS, "w", encoding="utf-8", newline="\n") as f:
        f.write("<!-- SPDX-License-Identifier: GPL-3.0-or-later -->\n\n")
        f.write("# Probe results\n\n")
        f.write(f"Run: {meta['when']}\n\n")
        f.write(f"Firmware / notes: {meta['fw'] or '(not recorded)'}\n\n")
        f.write("Generated by `tests/probe.py`. Every line below is an "
                "observation on real hardware, not an inference.\n\n")
        f.write("> Reminder: this device replies `1 200` to every well-formed "
                "frame, including ones it does nothing with. A 200 in these "
                "results is not evidence that anything happened.\n\n")
        for key, section, title, data in results:
            f.write(f"## `{key}` — {section}\n\n{title}\n\n")
            for k, v in data.items():
                v = str(v).replace("\r\n", " | ").replace("\n", " ")
                f.write(f"- **{k}**: {v[:400]}\n")
            f.write("\n")
    print(f"\nwritten: {RESULTS}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=proto.PID)
    ap.add_argument("--index", type=int, default=None)
    ap.add_argument("--media", default="RYUO_IV_HW_Info_02.mp4",
                    help="clip to keep playing during probes; the default is "
                         "an ASUS preset that ships on every unit")
    ap.add_argument("--only", nargs="*", help="probe keys to run")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for key, section, title, _ in PROBES:
            print(f"  {key:26} {section:5} {title}")
        return

    todo = [p for p in PROBES if not args.only or p[0] in args.only]
    if not todo:
        sys.exit(f"no probes matched {args.only}")

    print("=" * 74)
    print("  Ryuo IV probe harness")
    print("  Close ASUS Info Hub first. Keep an eye on the screen.")
    print("  `upgrade` is deliberately absent and is not going to be added.")
    print()
    print("  NOTE: this device replies `1 200` to everything, including")
    print("  resources it ignores and payload shapes it has no field for.")
    print("  The reply is NOT a validity signal. Only the panel counts.")
    print("=" * 74)
    fw = input("firmware version / any notes for the log (enter to skip) > ").strip()

    link = Link(args.vid, args.pid, args.index, args.media)
    results = []
    try:
        link.known_good()
        link.start_keepalive()
        print("\nkeepalive running (POST all every 1s) — take as long as you")
        print("like answering; the session will not lapse. Telemetry values")
        print("sweep, so a number that ISN'T moving is a stale slot.\n")
        for key, section, title, fn in todo:
            print(f"\n{'-' * 74}\n[{key}]  {section}  {title}\n{'-' * 74}")
            if ask("run this probe?", ("y", "n")) == "n":
                continue
            try:
                results.append((key, section, title, fn(link)))
            except KeyboardInterrupt:
                raise
            except Exception as ex:
                print(f"  !! probe raised: {ex}")
                results.append((key, section, title, {"error": repr(ex)}))
            link.known_good()
    except KeyboardInterrupt:
        print("\ninterrupted — saving what we have")
    finally:
        link.close()

    write_results(results, {
        "when": datetime.datetime.now().isoformat(timespec="seconds"),
        "fw": fw,
    })
    print("Paste it into an issue, or fold it straight into PROTOCOL.md.")


if __name__ == "__main__":
    main()
