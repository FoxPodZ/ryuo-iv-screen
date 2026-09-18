<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# ryuo-iv-screen — the ASUS ROG Ryuo IV screen protocol, reverse-engineered

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![AI Contribution](https://raw.githubusercontent.com/Essk/ai-contribution-level/main/badges/level-3.svg)](https://github.com/Essk/ai-contribution-level)

**An independent, hardware-verified description of the USB HID protocol behind
the AMOLED screen on the ASUS ROG Ryuo IV SLC AIO cooler**, reconstructed from
the official firmware. Every payload ASUS's own app sends is documented, and
the handful of things still unresolved are marked as unresolved rather than
guessed at.

**[PROTOCOL.md](PROTOCOL.md) is the point of this repository.** Frame format,
checksum, byte stuffing, every JSON payload the screen accepts, the widget
catalogue, the video pipeline and the limits it imposes, the burn-in machinery,
the OTA path — with the dead ends, the retracted guesses and the bugs in ASUS's
own renderer written down next to the parts that work. Everything in it was
worked out from the official 1.0.3 firmware package and confirmed live on the
cooler with `adb logcat`. No ASUS code is included or redistributed.

The Python scripts are the **reference implementation**: proof that the write-up
is right, and a proof of concept that happens to be good enough for daily use.
No service, no GUI, no installer, no kernel module, and nothing here touches the
cooler's firmware. If you want to write your own client in another language,
`ryuo_proto.py` plus PROTOCOL.md are the only two things you need.

*Where this is useful:* ASUS ships the screen with **Info Hub**, a Windows-only
app that isn't part of Armoury Crate and has no Linux counterpart. Without it
the panel loops a stock ASUS video forever. With the protocol written down you
can push your own telemetry, colours, widgets and media from Linux, Windows, or
anything that can open a hidraw node.

---

## What the teardown turned up

The findings that took the longest to establish, each written up in full:

* **The "screen" is a complete Android 13 computer** — Rockchip RK3562, codename
  `cm16`, shipped as a full OTA image inside the ASUS firmware zip, with an
  ODM-built launcher doing the drawing. [§11](PROTOCOL.md#11-device-side-notes)
* **`adb shell` gives an unauthenticated root prompt**, on a `user/release-keys`
  build with an unlocked bootloader and no dm-verity. That is the shipped
  configuration, not an exploit — see the
  [disclosure note](PROTOCOL.md#disclosure) for why it is stated openly.
* **The wire format is HTTP-shaped text inside 1024-byte HID reports**, framed
  with `0x5A` delimiters, byte stuffing and an additive checksum that is not a
  CRC despite being built by a function called `getCRC()`.
  [§2](PROTOCOL.md#2-frame-format)
* **The session is a dead-man's switch.** Stop sending telemetry for ~10 seconds
  and the screen reverts to stock — which makes a working client look broken the
  moment you stop to read something. [§10](PROTOCOL.md#10-post-all--telemetry)
* **Native-resolution video has to be HEVC.** The H.264 decoder declares
  1920×1088 on a 2240×1080 panel, and an oversized clip black-screens instead of
  erroring, because playback runs through Rockchip's `rockit` rather than
  MediaCodec. [§7](PROTOCOL.md#7-the-playmode-trap)
* **Burn-in protection blanks your widgets for 2 seconds every ~5 minutes**, and
  a long clip *reduces* the protection rather than the interruptions — the two
  are keyed to the same boundary. [§7](PROTOCOL.md#7-the-playmode-trap)
* **Six API fields are dead code**, four readouts render fine but have no tile
  in ASUS's picker, and two of ASUS's own widgets are visibly buggy.
  [§4](PROTOCOL.md#4-resources), [§10](PROTOCOL.md#10-post-all--telemetry)
* **The HID upload is a stub.** `transport` answers
  `{"state": "success", "blockMaxSize": 888888888}` and nothing ever receives
  the file, so media goes on over adb. Listing and deleting media do work over
  HID. [§4](PROTOCOL.md#4-resources)
* **The USB vendor id changes between firmware versions** while the product id
  stays put, so tools that match on the vendor id stop finding the cooler after
  an update. [§1](PROTOCOL.md#1-transport)

---

## What the protocol can do, and what the client implements

Everything below is documented in PROTOCOL.md and driven by the scripts here:

| Feature | Status |
| --- | --- |
| CPU / GPU / RAM / disk telemetry on-screen | ✅ |
| Six configurable widget slots (drag-and-drop equivalent) | ✅ |
| Label + value colours, per-zone | ✅ |
| Brightness (0–102) | ✅ |
| Custom media (mp4 / gif / still images) | ✅ — full-panel 2240×1080 video works in **HEVC**; H.264 is capped near 1920 wide |
| Playlists — Single / Random / Cycle | ✅ |
| Split screen (two independent zones) | ✅ |
| Live colour animation — hue cycle & thermal bands | ✅ |
| Celsius / Fahrenheit toggle | ✅ |
| Screen on/off (`waterBlockScreen`) | ✅ |
| Panel dim via `power` | ✅ `shutdown` dims it; which event restores it is unresolved |
| Screensaver via `displayInSleep` | ⚠️ toggling it puts `Screensaver.mp4` on screen; which value does it is unresolved |
| `rotate`, `waterfallMode`, `badges`, `align`, `position`, `color` | 💀 dead code — parsed, never used |
| Fan LCD | ⚠️ ACK, no observed effect |
| Animated overlay filter | ✅ — any non-empty `filter.value` turns it on; you can't pick which effect |
| Media listing (`conn`) | ✅ `ryuo_ctl.py ls` — presets and your files, no adb needed |
| Media delete (`mediaDelete`) | ✅ `ryuo_ctl.py rm`; the delete-everything-else mode is read from source |
| Media *upload* over HID | 💀 doesn't exist — `transport` replies "success" and never receives a byte. Use `adb push` |
| Pump control (`turboPump`) | 💀 targets a pump driver this board doesn't have |
| AMD GPU telemetry | ⚠️ only NVIDIA (`nvidia-smi`) is wired up so far |
| CPU temperature & fan speeds on Windows | ⚠️ Linux only — deliberately; see *Known limits* below |

---

## The hardware, briefly

The "screen" is a complete little Android computer glued to a water block.

| | |
| --- | --- |
| SoC | Rockchip **RK3562**, device codename `cm16` |
| OS | Android 13, full OTA image shipped inside the ASUS firmware zip |
| Panel | 2240×1080 (physically 1080×2240 portrait, rotated 90° by SurfaceFlinger), 60 Hz OLED — looks like a repurposed phone AMOLED. You can see it scan: full-frame flashes sweep left-to-right over ~16.7 ms |
| ODM | Baiyi (Shenzhen) — the UI app is `com.baiyi.homeui.hshomeui`, the transport is `com.baiyi.service.serialservice` |
| USB | `sys.usb.config=hid,adb` — device opens `/dev/hidg0`, host sees a hidraw node |
| USB IDs | product **`1C76`**, interface `MI_00`. Vendor is `0B05` or `1C75` **depending on firmware** — match on the product id |
| ADB | `adb shell` gives you an **unauthenticated root prompt** (`cm16:/ #`) |

> **Heads-up on the USB IDs.** The *vendor* id changes with firmware: `0B05`
> (ASUSTek) on 1.0.3 and 1.0.10, `1C75` (BYDevice, the ODM) on 1.0.7. The
> *product* id `1C76` is stable across all of them, so match on that — tools
> that pin the vendor id stop finding the cooler after a firmware update.
>
> And if you go looking for `0B05:19AF`, that's likely your motherboard's Aura LED
> controller, not the cooler. Since the cooler now also uses `0B05`, the
> product id is the only thing telling them apart.

### Getting a picture with scrcpy

`scrcpy` makes poking around this thing enormously nicer — but **it does not work
on defaults**. Out of the box it connects and then produces no frames at all,
with ffmpeg complaining it never got one.

The fix is to force the software encoder:

```bash
scrcpy --video-encoder OMX.google.h264.encoder
```

That's the whole fix — one flag, tested. (`--video-encoder` is the spelling
since scrcpy 2.0, when audio arrived and `--encoder` was split into a video and
an audio variant; 1.x calls it `--encoder`. You don't need `--video-codec`,
h264 is already the default.)

The problem is the encoder, and specifically it's a *declared limit* rather than
a broken one. Every h264 encoder on this build is capped under the panel's
2240 px width — including the Rockchip hardware one:

| Encoder | Declared max size |
| --- | --- |
| `c2.rk.avc.encoder` (Rockchip hardware) | 1920×1088 |
| `OMX.google.h264.encoder` (software) | 1280×720 |

The panel is 2240×1080. scrcpy screen-*records* the display, so its default
encoder selection asks `MediaCodecList` for something that can encode 2240×1080,
gets nothing back, and you get a session that establishes fine and streams zero
frames.

Naming the encoder is what fixes it — scrcpy then uses `createByCodecName()`,
which skips the capability check and hands the software encoder the frames
regardless. Software encoders generally cope well past their declared maximum.
You aren't selecting a better encoder; you're taking the one code path that
doesn't ask permission first.

The same mechanism bites on the decode side, which is why a native-resolution
clip has to be HEVC rather than H.264 — see
[PROTOCOL.md §7](PROTOCOL.md#7-the-playmode-trap).

If that doesn't do it on your unit, the other plausible cause is the content
not being on the display scrcpy looks at:

```bash
adb shell "dumpsys display | grep -iE 'mDisplayId|uniqueId|width=|height='"
scrcpy --display-id=1
adb shell "ls /vendor/lib*/omx* 2>/dev/null; getprop | grep -i codec"   # what encoders exist
```

Once it's up you get the full panel mirrored, and the factory app
(`com.baiyi.app.factorymode`, Chinese-only) becomes navigable instead of a wall
of 8px text. If you can't get video at all, you can still drive the UI blind:
`adb shell uiautomator dump /sdcard/ui.xml` gives you every element's bounds and
`adb shell input tap X Y` does the rest.

---

## Install

Python **3.8+** (tested on 3.11 and 3.12; the `hidapi` wheel may set a higher
floor than the code does on older interpreters).

```bash
pip install -r requirements.txt        # hidapi, psutil
```

`hidapi` needs udev permission to talk to the device:

```bash
sudo cp 70-ryuo.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

then replug the cooler. The shipped rule uses `TAG+="uaccess"`, which hands the
device to whoever is physically logged in and takes it back on logout — so no
`chmod 666` on a raw HID node that every process on the box can then write to.
If you're not on systemd, the file has a commented `plugdev` line instead. Or
just run as root.

**On Windows: close ASUS Info Hub first.** It holds the HID handle exclusively and you'll get nothing or broken behaviour until it's gone.

---

## Quickstart

```bash
# see what's actually enumerating (prints an index per interface)
python ryuo_send.py --list

# is the protocol talking? prints "1 200" with an empty body — spec is
# push-only, so an empty reply here means success, not failure
python ryuo_ctl.py get spec

# push a config and exit (screen reverts to stock after ~10s — that's expected)
python ryuo_send.py --config-only --items "CPU Temperature" "GPU Temperature" "Date&Time"

# the real thing: config + telemetry loop
python ryuo_send.py --items "CPU Temperature" "GPU Temperature" "Date&Time"
```

The device reverts to `standby.mp4` if it stops hearing from the host for ~10 seconds, so **the telemetry loop is also the keepalive**. There's no "set it and forget it" mode; something has to keep talking.

---

## Usage

### Widgets

Six fixed slots. Slot order == position on screen. Empty slots are `""`.

```bash
python ryuo_send.py --items "CPU Temperature" "CPU Load" "Memory Utilization" \
                            "GPU Temperature" "GPU Load" "Date&Time"
```

Valid item names (exact strings, case-sensitive):

```
CPU Load             CPU Usage            CPU Temperature
CPU Speed Average    CPU Voltage
GPU Load             GPU Usage            GPU Temperature
GPU Speed            GPU Power            GPU Voltage
Memory Utilization   Memory Frequency
Hard Disk Temperature                     Motherboard Temperature
Date&Time

Fan Speed <name>     <name> is any fans[].name you send -- see below
```

All sixteen confirmed rendering on hardware. There is no `Fan CPU` or
`Fan Chassis4`; fan readouts use the `Fan Speed <name>` form.

### Colours

```bash
python ryuo_send.py --title-color "#00FF9C" --content-color "#FFFFFF"
```

`titleColor` is the label (`CPU:`), `contentColor` is the value. Both go through Android's `Color.parseColor()`, so `#RRGGBB` and `#AARRGGBB` both work.

### Animated colours

```bash
# rainbow cycle, one full rotation every 5s
python ryuo_send.py --rgb both --rgb-mode hue --rgb-speed 0.2

# colour the text by CPU temperature, blinking red above 96C
python ryuo_send.py --rgb value --rgb-mode thermal --rgb-source cpu

# watch every band without cooking your CPU
python ryuo_send.py --rgb both --rgb-mode thermal --demo-temp -1
```

Thermal bands: `<34 °C` blue · `<61` green · `<81` yellow · `<96` red · `≥96` blinking light/dark red.

This works because colour updates go out on the `preset` resource, which repaints the text views **without** tearing down the video player. Sending a full `config` at 10 fps would restart the media every frame; `preset` doesn't.

### Media

Filenames only — the app resolves the directory itself:

* names starting with `RYUO` → `/sdcard/pcMediaPreset/` (ASUS's bundled clips)
* everything else → `/sdcard/pcMedia/` (yours)

⚠️ **Don't name your own files starting with `RYUO`** — it flips the lookup order
and you'll get the wrong clip. The match is also a substring test, not equality,
so avoid names that are prefixes of each other.

Getting your own files on there is just adb:

```bash
adb push my_clip.mp4 /sdcard/pcMedia/
python ryuo_send.py --media my_clip.mp4 --play-mode Single
```

**For full-panel video, encode HEVC at 2240×1080.** The Rockchip VPU decodes
H.265 up to 4096×2160 but H.264 only to 1920×1088, so native resolution works in
one and black-screens in the other:

```bash
ffmpeg -i in.mp4 -vf "scale=2240:1080:force_original_aspect_ratio=increase:flags=lanczos,setsar=1,crop=2240:1080" \
  -c:v libx265 -tag:v hvc1 -pix_fmt yuv420p \
  -crf 24 -maxrate 8M -bufsize 16M -preset slow -movflags +faststart -an out.mp4
```

`-tag:v hvc1` is required — rockit checks the fourcc. If you need H.264 for some
reason, stay at or under 1920 px wide (1920×926 is ASUS's own clip size). Stills are exempt —
`.png`/`.jpg` are copied through verbatim at any size. See
[PROTOCOL.md §7](PROTOCOL.md#7-the-playmode-trap).

Playlists and modes:

```bash
python ryuo_send.py --media a.mp4 b.gif c.png --play-mode Cycle
python ryuo_send.py --media a.mp4 b.mp4 --shuffle          # == --play-mode Random
```

Extension decides the player: `.mp4` → VideoView (advances at end of clip), `.gif` → Fresco one-shot (advances at end of gif), anything else → Glide still image (advances after a hardcoded 7 s). Missing files are silently skipped. Mixing all three in one playlist is fine.

> **Gotcha:** `playMode` accepts exactly `Single`, `Random`, `Cycle` — case-sensitive. Any other string passes the first check in the app and then falls through the second one with a bare `return`, leaving the player with no video path. You get a black screen and zero errors. See [PROTOCOL.md](PROTOCOL.md#7-the-playmode-trap).

### Split screen

```bash
python ryuo_send.py --media main.mp4 --media2 strip.png \
                    --items "CPU Temperature" "GPU Temperature" "Date&Time" \
                    --title-color2 "#FF00AA"
```

Passing `--media2` flips `screenMode` to `Screen Splitting`, at which point `media`, `playMode` and `settings` all become two-element lists (one per zone). The panel tiles as **1606×1080 + 634×1080** — zone 2 is hardcoded to 634 px in the app's layout and zone 1 takes the remainder. The 634 strip is the bit past the bend in the block. Note Info Hub's own crop tool enforces aspects matching 1600/640, so ASUS's tooling is 6 px out from ASUS's layout; it never shows because still images are drawn FIT_XY and stretched to fill regardless. See [PROTOCOL.md §8](PROTOCOL.md#8-split-screen).

`sysinfoDisplay` stays a flat 6-slot array, 3 slots per zone.

### One-off commands

`ryuo_ctl.py` sends a single request and pretty-prints whatever comes back. Handy for poking at things.

On its own it changes nothing durably — there's no keepalive, so the screen
reverts ~10 s later. To change a *live* session, run it alongside
`ryuo_send.py`; both can hold the hidraw node at once.

```bash
python ryuo_ctl.py get config
python ryuo_ctl.py get all
python ryuo_ctl.py get spec
python ryuo_ctl.py brightness 30       # 0-102; 100 is only ~98% of max
python ryuo_ctl.py items "CPU Temperature" "CPU Load" "Date&Time"
python ryuo_ctl.py raw POST temperature '{"value":"Fahrenheit"}'

python ryuo_ctl.py info                # firmware, hardware rev, capabilities (serial blanked)
python ryuo_ctl.py ls                  # what's in pcMediaPreset/ and pcMedia/
python ryuo_ctl.py rm old_clip.mp4     # delete from pcMedia/
python ryuo_ctl.py rm --except a.mp4 b.png   # delete everything in pcMedia/ but these
```

`rm` only ever touches `/sdcard/pcMedia/`, and refuses names with a path
separator. `rm --except` is read from source and hasn't been run on hardware.
It deletes every file you didn't name, so run `ls` first.

---

## Files

| File | What it is |
| --- | --- |
| `ryuo_proto.py` | The wire format: framing, checksum, byte-stuffing, and every payload schema. No I/O — import it and build your own thing. |
| `ryuo_send.py` | The daemon. Pushes config, then loops telemetry + colour animation. |
| `ryuo_ctl.py` | Single-shot request/response tool for exploring. |
| `PROTOCOL.md` | Full protocol writeup. |
| `70-ryuo.rules` | udev rule so you don't have to run as root. The number is load-bearing — `uaccess` tags are only honoured by rule files sorting before systemd's `73-seat-late.rules`. |
| `tests/test_proto.py` | Codec tests — framing, stuffing, checksum, payload shapes. No hardware needed. |
| `tests/probe.py` | Interactive harness for the unknowns in PROTOCOL.md. Sends one request at a time and writes down what you saw. |
| `tests/video_matrix.py` | Works out which video encodes actually play, holding the session open so a timeout can't masquerade as a decode failure. |
| `captures/` | Raw evidence — Info Hub logcats, the recovery transcript, the split-zone measurement — that the docs are checked against. |

If you're writing your own client in another language, `ryuo_proto.py` + `PROTOCOL.md` are the only two things you need.

---

## Known limits & dead ends

* **You cannot install apps on the cooler.** Don't waste the 3h+ like I did. The bundled PackageInstaller ships *only* `.UninstallActivity`. `pm install` verifies, stages and commits the session fine, then hangs forever waiting on a confirmation callback whose activity doesn't exist — and never returns an error. So no custom launcher, no third-party APKs, no on-device anything.
* **No useful on-device sensors.** hwmon on the board exposes `soc_thermal` plus factory test stubs (`test_ac`, `test_battery`, `test_usb`). There's no pump, fan or coolant sensor readable locally. All cooler telemetry has to come from the host.
* **The screen is host-bound by design.** It powers down with the PC and reverts to the stock loop ~10 s after the host stops talking. Nothing in the protocol changes that.
* **There is no upload over HID.** The protocol has `transport` / `transported`
  resources and the header schema has `FileName` / `FileSize` / `ContentRange`,
  but on this firmware nothing receives the data: `transport` replies "success"
  and that's all it does. MTP isn't enabled either, so `adb push` is the only
  way media gets on. Listing and deleting do work over HID (`ryuo_ctl.py ls`,
  `rm`). An earlier version of this README said the envelope supported
  uploads; it doesn't. See PROTOCOL.md §4.
* **Brightness saturates at 102, not 100.** The API value is multiplied by ≈2.5
  and handed to the kernel, which clamps at 255 — so `100` lands on 250, about
  98% of maximum, and true full brightness needs `102`. Info Hub never sends
  more than 100, so a stock cooler never runs its panel at full. Below that the
  driver scales 0-255 by exactly 13 into a 12-bit MIPI DSI register capped at
  3315/4095, leaving ~19% of the panel's range unused — sensible on an OLED.
  Measured against `/sys/class/backlight/`, not by eye; see PROTOCOL.md §4.
* **All 16 widget items are confirmed rendering on hardware** (label and value
  both, firmware 1.0.10), plus `Fan Speed <name>`. The `Fan CPU` /
  `Fan AIO Pump` / `Fan Chassis*` strings you might expect from Info Hub's
  picker **do not exist** — the real form is `Fan Speed CPU` and friends.
* **`POST all` is a dead-man's switch.** Stop sending it for ~10 s and the
  screen drops to standby — widgets gone, panel dimmed, `standby.mp4` playing,
  your media and your slots with it. Run the
  telemetry loop on a background thread from the moment you connect. If your
  changes work with Info Hub open and stop working when you close it, this is
  why: Info Hub was supplying the keepalive.
* **Your widgets will vanish for 2 seconds every ~5 minutes.** That's the OLED
  burn-in protection, not your client misbehaving: all six slots blank, the
  panel plays `Screensaver.mp4`, then everything returns. In split mode each
  zone does this on its own timer, with `Screensaver_left.mp4` and
  `Screensaver_right.mp4`. There's no way to turn it off — it's internal to the
  launcher.
* **Long clips quietly disable that protection.** The check only runs when media
  advances, so a 30-minute clip means the protect cycle fires every 30 minutes
  instead of every 5 — while the static widget text sits there unchanged the
  whole time. Clip length doesn't affect the burn-in risk, only the mitigation.
  If you care about the panel, prefer shorter items or a playlist. See
  PROTOCOL.md §7.
* **A slot with no matching telemetry keeps its previous value.** The label
  updates, the number doesn't, and nothing indicates it's stale — so a readout
  that silently stopped updating looks identical to one that works. Change
  something that should move and check that it moves.
* **Two renderer bugs, both confirmed on hardware:** `GPU Power` prints its
  unit as °C (the value is right, the unit is nonsense), and `GPU Usage` reads
  `gpu.load` so it renders the identical number to `GPU Load`. See
  PROTOCOL.md §10.
* **Four readouts have no tile in ASUS's picker at all** — `GPU Power`,
  `Memory Utilization`, `Memory Frequency` and `Hard Disk Temperature`. All
  four render perfectly; Info Hub simply never offers them.
* **GPU stats are NVIDIA-only** right now, via `nvidia-smi`. AMD would want a `sysfs`/`amdgpu` path in `_nvidia()`'s place. PRs welcome.
* **CPU temperature and fan speeds are Linux-only.** Both come from `psutil`,
  which only reads hardware sensors on Linux and FreeBSD. On Windows the
  `CPU Temperature` slot shows 0, and `Fan Speed …` slots get no data except
  what you pass with `--readout`. GPU temperature isn't affected: it comes from
  `nvidia-smi`, which works on both.

  This is deliberate. Windows has no built-in API that reliably reports the
  CPU's temperature. The one that exists, `MSAcpi_ThermalZoneTemperature`,
  needs admin and on most desktop boards returns a fixed or motherboard value.
  The real reading needs a kernel driver, which in practice means depending on
  a monitoring app such as LibreHardwareMonitor or HWiNFO, or loading that
  driver yourself as admin. That driver layer is also where the trouble has
  been: WinRing0, the driver most of these tools used for years, is now flagged
  by Microsoft Defender. This project stays at `hidapi` + `psutil`, with no
  admin rights and no third-party app, so on Windows the slot stays at 0
  rather than pulling any of that in.
* **Don't try to downgrade the firmware.** Info Hub will happily accept an older
  official firmware file and start the update — it has no downgrade check. The
  device does: recovery rejects it with `E3003` and nothing gets flashed, but
  the cooler is left sitting on a recovery screen. `adb reboot` gets you back.
* **Playback goes through `rockit`, Rockchip's own media framework**, which
  decodes on `rk_mpp` — the hardware VPU — not through Android's MediaCodec. So
  the `OMX.google.*` limits in `media_codecs.xml` describe a path playback never
  touches, which is why clips violating all of them play fine.
* **H.264 is a 1080p-class format on this SoC; HEVC isn't.**
  `c2.rk.avc.decoder` declares a maximum of **1920×1088** (2048×1080 plays
  anyway, 2240×1080 doesn't), while `c2.rk.hevc.decoder` declares **4096×2160**.
  Confirmed on hardware: **2240×1080 plays as H.265 and black-screens as H.264.**
  So use HEVC for full-panel video. A clip the VPU can handle is resolved by
  rockit's `RTConfigXML` and gets an `rk_mpp` decoder; one it can't falls
  through to `RTConfigMeta`, never acquires a decoder, and retries forever with
  no error — which is why an oversized H.264 clip shows nothing at all.
* **Same reason `scrcpy` needs its encoder forced:** `c2.rk.avc.encoder` maxes
  at 1920×1088 and the display is 2240 px wide, so the hardware encoder can't
  take the frame.
* Verified on a **Ryuo IV SLC 360 ARGB**, firmware **1.0.7 and 1.0.10**, and
  believed to hold for **1.0.3 – 1.0.10**: the on-device launcher version is
  identical across all three, so the protocol hasn't moved. What *did* change is the USB
  vendor id and some bundled media — see PROTOCOL.md §10b. Other Ryuo IV variants very likely use the same board and app; other ASUS coolers, no idea.

---

## Putting your own data on the screen

The item string for a fan readout is built at runtime as
`"Fan Speed " + <the name in your telemetry>`, and the label drawn is whatever
follows character 10 — so you control both halves. Any number you can measure
on the host goes on the panel under any label you like:

```bash
python ryuo_send.py \
  --readout Coolant=3229 \
  --readout "NAS Bay 3"=41 \
  --items "Fan Speed Coolant" "Fan Speed NAS Bay 3" "CPU Temperature"
```

Confirmed on firmware 1.0.10 — invented labels render with their values and the
unit `RPM`. There's no validation on the name at all.

The unit is always RPM, so it suits anything countable and lies about anything
else. Within that: pump RPM from a header ASUS doesn't read, a NAS temperature,
unread mail, build queue depth, days since the last incident. This is the only
route to a readout Info Hub cannot produce.

## Tests

```bash
pip install pytest
pytest tests/ -v                       # codec tests, no hardware needed
```

`tests/test_proto.py` pins the wire format, including the worked example printed
in PROTOCOL.md §2 as a golden vector — if the doc and the code ever drift apart,
that test fails.

For the things only hardware can answer:

```bash
python tests/probe.py --list           # what's still unknown
python tests/probe.py --only brightness_scale
python tests/probe.py                  # work through all of them

python tests/video_matrix.py           # which video encodes actually play
```

It sends one request, shows you the reply, asks what the screen did, and writes
`tests/probe-results.md`. It re-pushes a known-good config between probes so a
bad value can't leave you guessing. `upgrade` is deliberately not in there.

## How this was made

The reverse-engineering is mine: pulling apart the 1.0.3 firmware package,
working out it was an Android OTA, getting an adb root shell, decompiling
`SerialService.apk` and `HomeUI.apk`, finding the framing in
`SerialMsgManager`, tracking down which USB device was actually the cooler,
and testing every one of these behaviours on real hardware.

The client code and this documentation were written through interactive
prompting with an AI assistant and then verified against the device — that's
[**Level 3 (Interactive)**](https://github.com/Essk/ai-contribution-level) on
the AI contribution scale. Nothing in here is claimed to work that hasn't been
run; anything I *haven't* confirmed is explicitly marked as untested in
[PROTOCOL.md](PROTOCOL.md).

## Disclaimer

Unofficial, unaffiliated with ASUS or Baiyi.

No ASUS or Baiyi firmware, APKs, or decompiled source files are redistributed
here. What this repo contains is a *description* of how the device behaves,
produced for the purpose of interoperability, plus a handful of identifiers —
field names, string constants, message numbers — quoted where naming the actual
thing is clearer than describing it. Where control flow is shown in code-like
form it is a paraphrase, not a copy.

Decompilation for interoperability is permitted in the EU (Software Directive
2009/24/EC Art. 6; §69e UrhG in Germany) and has been recognised as fair use in
the US for the same purpose (*Sega v. Accolade*, *Sony v. Connectix*). Both
come with conditions: what you learn is used for interoperability, is passed on
only as far as interoperability needs, and doesn't go into a look-alike
program. A protocol description so that independently written clients can talk
to the device is exactly that — and it is why none of their code is here. If
you want to verify any of this, decompile your own copy from the firmware ASUS
publishes.

Nothing in this repo modifies the cooler's firmware; it only speaks the
protocol the stock software already speaks. But you're running unofficial
software against an expensive cooler, so — your warranty, your call.

## Licence

**[GNU GPL v3 or later](LICENSE)** (`GPL-3.0-or-later`), for the whole
repository — code, docs and captures alike — with an attribution term under
§7(b). Do what you like with it, including commercially; keep it open, and keep
my name on it. Details in
[LICENSE-ADDITIONAL-TERMS.md](LICENSE-ADDITIONAL-TERMS.md).

<details>
<summary>Why this licence and not MIT or AGPL</summary>

**Not MIT**, because the whole point of the work is that this stayed closed for
no good reason. I'd rather it not get quietly absorbed into someone's
closed-source fan-control suite.

**Not AGPL**, because AGPL puts a lot of people off, and engineers at companies
whose policy bans it — Google's is the famous one — simply can't touch AGPL code
even if they own this cooler and want to help. That's a real cost for a network
clause that would never fire anyway: this is a local USB daemon talking to a
water block, there is no network service to trigger it.

**GPL v3 or later** is the middle: closed forks are out, contributors are in.

</details>

The **protocol itself is not covered by this** — it's a set of facts about
someone else's hardware, not my creative work. Clean-room reimplement it in
whatever language under whatever licence you want. That's the point of writing
it down.
