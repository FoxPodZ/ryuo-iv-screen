<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# The Ryuo IV screen protocol

Reconstructed from the official firmware package (`ROG_RYUO_IV_Series_Firmware_File.zip`, v1.0.3), which turns out to be a full Android 13 OTA for a Rockchip RK3562 board codenamed `cm16`.

Two APKs matter:

| APK | Package | Role |
| --- | --- | --- |
| `SerialService.apk` | `com.baiyi.service.serialservice` | Transport. `SerialMsgManager.sendRequestMsg()` does the framing, `ByteTools.getCRC()` / `int2Bytes()` do checksum and length, `android_hidport_api.HidManage` does the USB side and the 1024-byte padding. |
| `HomeUI.apk` | `com.baiyi.homeui.hshomeui` | The UI. `entity/Pc*.java` are the payload schemas, `manage/MsgReceiverManager.java` is the command dispatch, `MainActivity`'s handler cases do the actual work. |

Everything below was then confirmed live against the hardware via `adb logcat` while ASUS Info Hub was driving it — so the schemas are what Info Hub *actually sends*, not guesses from field types.

---

## 1. Transport

The screen's USB gadget runs `sys.usb.config=hid,adb`. Device side opens `/dev/hidg0`; host side gets a hidraw node at product id **`1C76`, interface `MI_00`**. The *vendor* id depends on firmware — see below.

Report ID `0x00` and `0x01` both work — prepend one byte before the write, hidapi expects it.

Reports are **1024 bytes**. Frames are zero-padded up to a multiple of that before writing, and long frames are simply written as consecutive 1024-byte chunks.

---

### The vendor id changes between firmware versions

Match on the **product id**. It is stable; the vendor id is not.

| Firmware | USB ID | Vendor | Product string |
| --- | --- | --- | --- |
| 1.0.3 | `0B05:1C76` | ASUSTek | `HID Interface` |
| 1.0.7 | `1C75:1C76` | BYDevice (Baiyi, the ODM) | `HID Interface` |
| 1.0.10 | `0B05:1C76` | ASUSTek | `ROG RYUO IV Standard` |

So **1.0.7 is the odd one out** — it shipped under the ODM's own vendor id and
later firmware went back to ASUS's. Any tool matching on the vendor id works on
one firmware and silently stops finding the device after an update. That is not
hypothetical; it is what happened to this repository's own scripts when a
1.0.7 unit updated to 1.0.10.

`ryuo_proto.find_devices()` enumerates on the product id and accepts either
vendor, and the shipped udev rule has a line for each.

> ⚠️ **This makes the `19AF` warning sharper, not weaker.** `0B05:19AF` is likely the
> motherboard's Aura LED controller. Now that the cooler *also* uses `0B05`,
> the product id is the **only** thing separating them. Never relax a match to
> the vendor id alone.

The product string is worth knowing too: `ROG RYUO IV Standard` on 1.0.10 is a
far better identifier than the generic `HID Interface` older firmware reports —
and the word *Standard* suggests ASUS expects other variants to exist.


## 2. Frame format

```
5A | stuffed( LEN | BODY | CKSUM ) | 5A
```

| Field | Size | Notes |
| --- | --- | --- |
| `0x5A` | 1 | start delimiter |
| `LEN` | 2 | **big-endian**, equals `len(BODY) + 5` |
| `BODY` | n | see §3 |
| `CKSUM` | 1 | `sum(LEN + BODY) & 0xFF` — an additive sum, despite the method being called `getCRC()` |
| `0x5A` | 1 | end delimiter |

Byte-stuffing applies to `LEN | BODY | CKSUM` only, never to the delimiters:

```
0x5A  ->  5B 01
0x5B  ->  5B 02
```

### Worked example

`GET spec` with `SeqNumber=1`:

```
5A 00 43 47 45 54 20 73 70 65 63 20 31 0D 0A 43
6F 6E 74 65 6E 74 54 79 70 65 3D 6A 73 6F 6E 0D
0A 43 6F 6E 74 65 6E 74 4C 65 6E 67 74 68 3D 30
0D 0A 53 65 71 4E 75 6D 62 65 72 3D 31 0D 0A 0D
0A D0 5A
```

* `5A` — start
* `00 43` — LEN = 67; body is 62 bytes, 62 + 5 = 67 ✔
* the ASCII middle — the body (§3)
* `D0` — checksum
* `5A` — end

...then padded with `0x00` out to 1024 bytes.

---

## 3. Body: HTTP over USB HID

They reimplemented HTTP. Genuinely.

**Request:**

```
<METHOD> <resource> 1\r\n
Key=Value\r\n
...
\r\n
<payload>
```

**Response:**

```
<version> <status>\r\n      e.g.  1 200
Key=Value\r\n
...
\r\n
<payload>
```

Methods: `GET`, `POST`, `DELETE`, `STATE`.

Header keys (`DataHeader` fields — any field set to `-1` is omitted rather than sent):

| Key | Purpose |
| --- | --- |
| `SeqNumber` | your sequence number |
| `AckNumber` | device echoes `SeqNumber + 1` |
| `ContentLength` | byte length of the payload |
| `ContentType` | always `json` in practice |
| `FileName`, `FileSize`, `ContentRange` | chunked media upload over this same envelope |
| `Counter`, `Date`, `msgId` | seen in the schema, unused by the paths documented here |

Payload is JSON, `ContentLength` bytes of it.

---

## 4. Resources

Everything `MsgReceiverManager` dispatches on:

| Resource | Payload | Status |
| --- | --- | --- |
| `all` | `PcInfo` telemetry blob (§10) | ✅ tested on device |
| `config` | full session setup (§6) | ✅ tested on device |
| `preset` | `ScreenConfig`, live repaint (§9) | ✅ tested on device |
| `spec` | `{"cpu": str, "gpu": str}` — model-name labels | ✅ tested (push-only, see below) |
| `sysinfoDisplay` | `{"items": ["CPU Temperature", ...]}` | ✅ tested on device |
| `brightness` | `{"value": 0-102}` — 100 is only 98% of max, saturates at 102 | ✅ measured against the kernel backlight |
| `temperature` | `{"value": "Celsius"\|"Fahrenheit"}` | ✅ tested on device |
| `disconn` | none — host leaving, reverts to stock loop | ✅ tested on device |
| `waterBlockScreen` | `{"enable": bool}` → `doBlockScreen()` — screen on/off | ✅ tested on device |
| `displayInSleep` | `{"enable": bool}` — toggling it enabled puts `Screensaver.mp4` on screen and stops showing values until disabled. (fw 1.0.7) | ✅ tested on device |
| `waterBlockScreenId` | a full `ScreenConfig` — same shape as `preset` | 📖 payload read from source, untested |
| `power` | `{"event": "shutdown"}` dims the panel. Which event, if any, restores it is unresolved — see below | ✅ tested on device |
| `fanLCD` / `fanLCDSet` | `{"speed": str, "mode": str}`; the `FanLCD` entity also has `fixedMode` (int) and `smartMode` (`int[][]`) | 📖 payload read from source, untested |
| `upgrade` | an update zip — the handler just logs `update.zip save!!!` and stages it. Signature-checked in recovery; downgrades rejected there (E3003), not by Info Hub | ☠️ **do not poke** |
| `rotate` | `{"degree": <int>}` — writes `persist.vendor.orientation`; the property sticks, the panel does not turn | 💀 **dead, confirmed on device** |
| `waterfallMode` | `{"enable": bool}` — parsed and dispatched, handler logs and returns | 💀 **dead, not unknown** |

> ⚠️ **`1 200` does not mean "accepted".** This device replies `1 200` to every
> well-formed frame, including resources it ignores and payload shapes it has no
> field for. `rotate` returns 200 for `{"value": 90}`, `{"angle": 90}`,
> `{"rotate": 90}` and `{"value": "90"}` alike and does nothing for any of them.
> The status confirms the *framing* parsed. Nothing more. Only the panel tells
> you whether something worked.

**Five markers, and they mean different things.**

- ✅ — actually sent to hardware and observed working.
- 📖 — the handler was read in `MsgReceiverManager` and the field names are real, but nobody has sent one. Field names good, behaviour unverified.
- ⚠️ — partially understood: either the string appears in the dispatch table and
  nothing more, or something was observed once but not cleanly enough to rely on.
- 💀 — dead code. Parses, dispatches, replies `1 200`, and does nothing. Not an
  unknown; an answered question.
- ☠️ — probably don't send this.

If you test one, open an issue or a PR and it gets promoted.

### Brightness: the documented 0-100 range can't reach full brightness

Three layers, and the interesting part is the seam between the first two.
Measured on firmware 1.0.7 by sending each value and reading
`/sys/class/backlight/*/brightness` back over adb:

| API value | kernel backlight | DCS register | % of max |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0% |
| 10 | 26 | 338 | 10.2% |
| 25 | 63 | 819 | 24.7% |
| 50 | 126 | 1638 | 49.4% |
| 75 | 187 | 2431 | 73.3% |
| 85 *(Info Hub's default)* | 212 | 2756 | 83.1% |
| **100** | **250** | **3250** | **98.0%** |
| **102+** | **255** | **3315** | **100%** |
| 125 / 150 / 200 / 255 | 255 | 3315 | 100% |

**The app does not clamp at 100.** It multiplies by ≈2.5 and passes the result
down; the *kernel* clamps at 255. So `{"value": 100}` lands on 250 — five
backlight steps short of maximum — and the last 2% needs **`{"value": 102}`**.

That is a real, measurable difference, not a rounding artefact: 250 → 255 is
DCS 3250 → 3315, about 2% more backlight. It is small enough to be genuinely
arguable by eye, which is exactly why two earlier probe runs disagreed about
it, and why it was written off as an illusion during investigation. It wasn't.
Reading the number settled what argument couldn't.

> **If you want true maximum brightness, send 102, not 100.** Nothing above 102
> does anything further. Info Hub never sends more than 100, so a stock cooler
> never runs its panel at full — which may well be deliberate on an OLED.

#### The ±1 wobble is Android, not the panel

The scale factor is 2.50, but the measurements don't sit on it cleanly — 10→26
and 50→126 are each one *over*, 75→187 and 85→212 are one *under*. That isn't a
gamma curve. `mBrightnessToBacklightSpline` in `dumpsys display` is the
identity, `[(0.0, 0.0), (1.0, 1.0)]` — no mapping table at all.

It's a denominator mismatch, visible directly in the dump:

```
mBrightnessRampFastDecrease        = 0.70472443   = 179/254
mBrightnessRampSlowDecrease        = 0.23228346   =  59/254
mScreenBrightnessForVrRangeMinimum = 0.30708700   =  78/254
mCachedBrightnessInfo.brightness   = 0.19291338   =  49/254
Display Brightness                 = 0.19607846   =  50/255   <-- different!
```

Two denominators in one subsystem. That's Android 11+'s brightness rework: the
internal representation is a float 0.0-1.0, and the framework's own legacy int
scale is defined over **1-255, not 0-255** — its `float → int` is
`round(1 + f × 254)`. But the value arriving *into* that framework here has
been computed on the plain 0-255 scale: the `Display Brightness = 50/255` line
above is the tell. So the trip is `i/255` on the way in and `round(1 + f × 254)`
on the way back out, and a value crossing that boundary picks up a rounding
step against mismatched ranges. (Had both directions used the 1-255 scale, the
round trip would be an identity and there would be no wobble to explain.)

Modelling it as `floor(api × 2.5)` → `i/255` → `round(1 + f × 254)` reproduces
**every measured point except one**:

| API | measured | model | plain `round(×2.5)` |
| --- | --- | --- | --- |
| 10 | 26 | ✅ 26 | 25 |
| 25 | 63 | ✅ 63 | 62 |
| 50 | 126 | ✅ 126 | 125 |
| 75 | 187 | ✅ 187 | 188 |
| 85 | 212 | ✅ 212 | 212 |
| 100 | 250 | ✅ 250 | 250 |
| 0 | 0 | ❌ 1 | 0 |

The `×2.5` values land on `.5` boundaries at exactly 25 and 75 (62.5, 187.5)
and on an exact integer at 50 (125.0) — precisely where a ±1 round-trip error
is most likely, and precisely where the readings drift.

The single miss is instructive rather than damaging: `round(1 + f × 254)` cannot
return 0, so a zero path *must* be special-cased somewhere. The formula predicts
that an exception has to exist exactly where one does.

> ✅ **The model was fitted to seven points and then tested against fourteen it
> had never seen. It got all fourteen exactly right.**
>
> | API | predicted | measured | | API | predicted | measured |
> | --- | --- | --- | --- | --- | --- | --- |
> | 1 | 3 | **3** | | 98 | 245 | **245** |
> | 2 | 6 | **6** | | 99 | 247 | **247** |
> | 3 | 8 | **8** | | 100 | 250 | **250** |
> | 4 | 11 | **11** | | 101 | 252 | **252** |
> | 5 | 13 | **13** | | 102 | 255 | **255** |
> | 95 | 237 | **237** | | 103 | 255 | **255** |
> | 96 | 240 | **240** | | | | |
> | 97 | 242 | **242** | | | | |
>
> Twenty-one points, no misses, including the awkward low end where the `+1`
> offset appears and the knee at 101→252 / 102→255 where saturation begins.
> A fitted curve can survive its training data by luck; surviving fourteen
> unseen predictions it was committed to in advance is a different claim.
>
> Re-run it yourself with `tests/probe.py --only brightness_precision`, which
> prints `ok` or `MISMATCH` per row. Firmware 1.0.10.

So: the DCS stage below is perfectly linear with no exceptions, and the noise
above it is Android's float/int round-tripping. Neither the panel nor this
protocol is doing anything strange.

### Below that: the kernel and the panel

The panel driver takes 0-255 and scales it by exactly 13 into a MIPI DSI
`set_display_brightness` (DCS `0x51`) command. Straight from `dmesg`:

| `oled_backlight_update_status` | `dsi_dcs_bl` set value | ÷ |
| --- | --- | --- |
| 255 | 3315 | 13.0 |
| 250 | 3250 | 13.0 |
| 51 | 663 | 13.0 |

Perfectly linear. The DCS register is 12-bit (max 4095) and they stop at 3315,
so **about 19% of the panel's range is never used at all** — which, on an OLED
with a burn-in protection system bolted on, reads as a deliberate lifetime
decision rather than an oversight.

Stacking the two: one API unit is ≈32.5 DCS units, and the whole usable API
range 0-102 maps onto 0-3315 of a possible 0-4095.

**This also explains `saveBright = 125`.** That cached constant was read as
proof the API was 0-255, which is what sent the investigation down the wrong
path for a while. The constant isn't wrong — it's in *kernel* units, where
125/255 is a sensible default. The error was assuming one number meant every
layer shared a scale.

To reproduce any of this:

```bash
adb shell ls /sys/class/backlight/
python tests/probe.py --only brightness_scale     # sweeps 0-255, reads each back
```

### `rotate` — the handler works, the feature doesn't

The whole handler, described rather than quoted: read the integer under the
key `degree` out of the payload, write it as a string into the system property
`persist.vendor.orientation`, return. Nothing repaints, no view is touched.

Everything about that works exactly as written, confirmed on firmware 1.0.10:

* `{"degree": 180}` sets `persist.vendor.orientation` to `180`, immediately.
* `90` and `0` likewise. The value **survives a reboot**, as a `persist.`
  property should.
* The wrong key — `{"value": 180}` — leaves the property untouched while still
  replying `1 200`, because `getInt` on a missing key throws into a catch block
  that logs and returns.

**And the panel never rotates.** Property set to 180, confirmed with `getprop`,
rebooted, read back as 180 afterwards — display unchanged. So the property is
written, persisted, and read by nothing.

The likely reason is in the build properties: display orientation comes from
`ro.surface_flinger.primary_display_orientation=ORIENTATION_90`, which is how a
portrait phone panel ends up presenting as 2240×1080 landscape in the first
place. A `ro.` property is fixed at build time and cannot be overridden at
runtime, so for `persist.vendor.orientation` to do anything, something would
have to read it and act — an init script, a vendor HAL, a rotation-aware
launcher. On this build, nothing does.

> This is the most thoroughly tested dead end in the document, and it is worth
> noting *why* it took so long to reach. Six guessed payload keys across two
> probe runs found nothing, which looked like "we haven't found the right
> key yet". Reading the source produced the right key and a mechanism, which
> looked like a discovery. It took setting the property, rebooting, and reading
> it back to establish that the correct key applied to a working handler still
> achieves nothing.
>
> On the strength of the source read alone, this looked like a usable feature
> for mounting the block with the tubes on the other side. It isn't. The dead
> end is written up rather than dropped, because "the handler works and the
> feature doesn't" is a distinction worth being able to make.

### `power` — `shutdown` dims the panel; what restores it is unresolved

`doPower(event)` switches on a string. Tested on firmware 1.0.7 with `sleep`,
`wake`, `shutdown`, `standby` and `resume`:

* **`shutdown` dims the panel**, to roughly 20 brightness. That was watched
  happen, directly, and it stands.
* `sleep`, `wake` and `resume` did nothing visible.
* The panel came back afterwards — and *what brought it back* is the part that
  is not pinned down. The run credited one of the other events, but every probe
  is followed by a `known_good()` config push, and a full `config` carries
  `brightness` (§6), so the restore could have been the event, the config, or
  both. Which event string, if any, undoes `shutdown` is an open question; so
  is whether anything beyond those five is a valid event at all.

`tests/probe.py --only power_events` now runs under a keepalive, dims the panel
with `shutdown`, and then tries each candidate event **without** a config push
in between, so an event that restores brightness can be told apart from the
config that would otherwise have done it.

### Dead code: `rotate`, `waterfallMode`, `badges`, `align`, `position`, `color`

Not unknown — **implemented and then abandoned**. Two resources and four
`PmSetting` fields that parse correctly, dispatch correctly, reply `1 200` and
do nothing at all. Worth documenting so nobody else spends an evening on them.

`rotate` is the subtlest of the group because its handler genuinely runs and
genuinely writes a property; only the consumer is missing. See above.

`waterfallMode` parses `{"enable": bool}` and dispatches it properly to handler
case 116 — whose entire body is a debug log line naming
`MSG_WATERFALLMODE_CHANGE`, followed by a return. It logs. That is the entire
implementation.

`badges` is a `List<String>` on `PmSetting` with a getter, a setter and a
`toString()`, and **no reader anywhere in the app**. That is why it is `[]` in
every captured frame — nothing would ever put anything in it.

The same grep turned up three more `PmSetting` fields in the same state:
`align`, `position` and `color` (distinct from `titleColor` / `contentColor`).
`getAlign()`, `getPosition()` and `getColor()` are never called. They are
leftovers from an earlier settings schema the current renderer ignores.

**Of everything in `settings`, only `titleColor`, `contentColor` and
`filter.opacity` are live.**

### A developer test harness left in the shipping build

`MainActivity.onCreate` installs a click listener that injects a canned
`ScreenConfig` plus a canned `PcInfo` and refreshes 1000 ms later. Tap the right
view and the UI populates with fake data — that is how the renderer was tested
without a PC attached, and it was never taken out.

Two things fall out of it. The canned config is a **hardcoded preset** with the
id `Pre-set 1: Cooling delivery`, a `settings` block that still populates the
dead `color` / `align` / `position` fields (§4), and a six-slot `sysinfoDisplay`
of `CPU Temperature`, `GPU Temperature`, `CPU Speed Average`, `GPU Speed`,
`CPU Load` and `GPU Load`.

All six of those strings are in the item list in `ryuo_proto.py`, which is the
first independent confirmation that list is right — ASUS's own code uses them.

And the canned `PcInfo` carries a fan entry shaped
`{"type": "Fan", "name": "Fan CPUFANIN0", ...}`. **`Fan` has a `type` field that
Info Hub never sends**, and the name format is richer than the bare `"CPU"` in
the captures. Neither turned out to explain the widget behaviour — fan readouts
are built from `"Fan Speed " + fans[].name`, and `Fan CPU`-style strings simply
do not exist (§10) — but the `type` field is real and undocumented regardless.

### `spec` is push-only

`GET spec` returns `1 200` with an **empty body**. The device stores the CPU/GPU name strings you push and renders them as labels; it has no way to discover them itself, so there's nothing to read back until you've sent some. Useful as a liveness check, useless as a query.

### Keepalive

If the device doesn't hear from the host for roughly **10 seconds**, it drops to standby: the widget labels and values disappear, the panel dims (by an amount nobody has measured yet), and `standby.mp4` plays until something talks to it again — the same state as a fresh boot. There is no persistent-config mode: whatever is driving the screen has to keep sending. `POST all` on a 1 s interval doubles as the heartbeat.

On a clean shutdown, send `POST disconn` so it reverts immediately instead of showing a stale frame for ten seconds.

---

## 5. Real captured traffic

Everything below is from `adb logcat` on the cooler while genuine ASUS Info Hub
drove it. This is the ground truth the rest of this document is checked against;
the raw log is in [`captures/infohub-capture.log`](captures/infohub-capture.log), with
the capturing host's CPU/GPU names and RAM/disk sizes replaced by placeholders.
Nothing structural was touched.

Info Hub's `POST config` on connect, verbatim:

```json
{"temperature":"Celsius","waterBlockScreen":{"enable":true,"displayInSleep":true,
"brightness":85,"id":{"id":"Customization","screenMode":"Full Screen",
"playMode":"Single","media":["RYUO_IV_HW_Info_02.mp4","RYUO_IV_HW_Info_05.mp4",
"RYUO_IV_HW_Info_01.mp4","RYUO_IV_HW_Info_03.mp4","RYUO_IV_HW_Info_04.mp4"],
"settings":{"titleColor":"#E5252B","contentColor":"#FFFFFF",
"filter":{"value":null,"opacity":100},"badges":[]},
"sysinfoDisplay":["CPU Temperature","GPU Temperature","","","",""],
"timeZone":"Europe/Berlin"}},
"spec":{"cpu":"<host CPU model>","gpu":"<host GPU model>"}}
```

Three things fall out of that one line:

1. **`sysinfoDisplay` is a fixed 6-element array and the index is the position.**
   There are no coordinates anywhere in `settings`. Info Hub's "drag the widget
   where you want it" is really "pick one of six predefined slots", and `""`
   means the slot is off. A config with only two non-empty entries has four
   dead slots, which is why a third widget can silently fail to appear.
2. **`brightness` here is 85**, on the same scale the standalone `brightness`
   resource uses — nominally 0-100, actually 0-102 (§4).
3. **`ScreenConfig` has fields Info Hub never populates.** The app's own
   `toString` prints `ScreenConfig{Type='null', ..., ratio='null', ...}` — both
   were `null` in every captured frame. `Type` is still unknown. `ratio` is
   not: it works, and it is a second feature ASUS's software never exposes.

   `case 105` switches on `1:1` / `2:1` / `3:1` / `4:3` / `16:9`.

   ⚠️ **The table below is the weakest evidence in this document.** It comes
   from runs that predate both the media-settle gate and the keepalive fix, and
   it is internally inconsistent: the same run reported `ratio: null` as
   "rescaled", which cannot be right, since null is the baseline every other row
   is being compared against. The answers were also given relative to the
   previous state rather than as absolute descriptions. Treat the shape as
   indicative and the cells as unverified until a clean run replaces them —
   `tests/probe.py --only screen_config_type_ratio` now gates on the panel
   having settled and asks for absolute states.

   Tested on firmware 1.0.7, across two runs:

   | `ratio` | Still image | Video |
   | --- | --- | --- |
   | `"1:1"` | ✅ rescaled | ✅ rescaled |
   | `"4:3"` | ✅ rescaled | no visible change |
   | `"16:9"` | ✅ rescaled | no visible change |
   | `"2:1"` | ✅ default | ✅ default |
   | `"3:1"` | no visible change | no visible change |
   | `null` | baseline | baseline |

   > **`ratio` does not black-screen video**, despite an early run suggesting it
   > did. `1:1` rescales video fine and the rest render normally. Those black
   > screens were the panel still loading media when the question was asked,
   > which the same run demonstrated independently: the tester noticed mid-probe
   > that an image had only just appeared, several answers late. Media load
   > latency on this device exceeds the 2.5 s settle that probe was using, and
   > several of its results are contaminated by it.

   All widgets continued to render with a ratio active. An earlier probe run
   had suggested only `CPU Temperature` survived; that was the same media-lag
   contamination, not a real effect.

Also visible in the same capture, worth knowing before you debug something that
isn't broken:

- The device clock is wrong until a host connects — log lines start at `01-21`
  and jump to `09-07` the moment Info Hub attaches. It has the `SET_TIME`
  permission and uses it.
- **Info Hub sends one all-zeros telemetry frame immediately after `config`**,
  before any real numbers. If your first frame looks empty, that's normal
  behaviour being imitated, not a bug.

## 6. `POST config`

The big one. This is what Info Hub sends on connect.

```jsonc
{
  "temperature": "Celsius",              // or "Fahrenheit"
  "waterBlockScreen": {
    "enable": true,
    "displayInSleep": true,
    "brightness": 85,                    // Info Hub's default; same 0-102 scale as the standalone resource (§4)
    "id": { /* ScreenConfig, see below */ },
    "fanLCD": { "speed": "", "mode": "" }
  },
  "spec": { "cpu": "<host CPU model>", "gpu": "<host GPU model>" }
}
```

### ScreenConfig

```jsonc
{
  "id": "Customization",
  "screenMode": "Full Screen",           // see §8
  "playMode": "Single",                  // see §7
  "media": ["clip.mp4"],
  "settings": {
    "titleColor":   "#E5252B",           // the "CPU:" label
    "contentColor": "#FFFFFF",           // the value
    "filter": { "value": null, "opacity": 100 },
    "badges": []
  },
  "sysinfoDisplay": ["CPU Temperature", "GPU Temperature", "Date&Time", "", "", ""],
  "timeZone": "Europe/Berlin"
}
```

Colours go through `Color.parseColor()`, so `#RRGGBB` and `#AARRGGBB` both work.

`config` lands in `MainActivity` case **105**, which hides `mainParent`, tears down the video player and rebuilds everything. Case 14 does a `postDelayed(doBlockScreen, 1000L)` on top of that, so give it **~1.6 s to settle** before sending anything else. Sending `config` repeatedly restarts the media every time — that's what `preset` is for.

### Widget slots

Six fixed slots. Index in the array == position on screen. `""` leaves a slot empty. This is exactly what the Info Hub drag-and-drop UI produces.

Valid strings — all sixteen confirmed rendering on hardware, plus the dynamic
fan form. Field sources and units are tabulated in §10:

```
CPU Load             CPU Usage            CPU Temperature
CPU Speed Average    CPU Voltage
GPU Load             GPU Usage            GPU Temperature
GPU Speed            GPU Power            GPU Voltage
Memory Utilization   Memory Frequency
Hard Disk Temperature                     Motherboard Temperature
Date&Time

Fan Speed <name>     where <name> is any fans[].name you send
```

---

## 7. The `playMode` trap

`playMode` accepts **`Single`**, **`Random`**, **`Cycle`**. Case-sensitive. Anything else black-screens the device with no error, and it took a while to work out why: **two different comparisons** decide the behaviour.

Paraphrased from the decompiled dispatch — this is a description of the control
flow, not a quote:

```
// onCompletion (main_video1)
if (playMode.equals("single"))   // lowercase!
    return;                      // do nothing
else
    post(MSG_HANDEL_MEDIA);      // = 102

// case 102
"Single" -> replay media[0]
"Random" -> random index
"Cycle"  -> next index, wrapping
default  -> bare return          // <-- no video path is ever set
```

An unrecognised string sails past the first check (it isn't lowercase `"single"`), reaches case 102, matches nothing, and hits the bare `return`. The player is left with no path. Black screen, no log line, no error response.

Related: `--play-mode Random`/`Cycle` with an **empty** media list black-screens for the same structural reason. If you're not supplying media, use `Single`.

### Media resolution

`media[]` carries **bare filenames**; `MainActivity.getMediaFilePath()` picks the
directory from three path constants — a base path and a custom path that are
both `sdcard/pcMedia/` (your uploads), and a preset path of
`sdcard/pcMediaPreset/` (ASUS's shipped clips).

(Yes, relative — no leading slash. It resolves from the process working
directory and happens to land in the right place.)

The resolver dispatches on a literal prefix check:

- name starts with `RYUO` → look in `pcMediaPreset/`, fall back to `pcMedia/`
- anything else → look in `pcMedia/`, fall back to `pcMediaPreset/`

"Look in" means listing the directory and testing `entry.contains(name)` — a
**substring** match, not equality, so a file whose name is a prefix of another
can resolve to the wrong one.

> ⚠️ **Don't name your own files starting with `RYUO`.** It flips the lookup
> order and you'll spend a while wondering why the wrong clip is playing.

Getting files on there is just `adb push my_clip.mp4 /sdcard/pcMedia/`.

**Native-resolution video works, but only in HEVC.** A 2240×1080 H.265 clip
plays; the identical frame in H.264 black-screens. ASUS's own media sidesteps the
question by being smaller than the panel:

| Source | Resolution | Ratio |
| --- | --- | --- |
| ASUS's bundled `RYUO_IV_HW_Info_*.mp4` | **1920×926** | 2.0734 |
| Info Hub's transcode of user uploads | **1850×924** | 2.0022 |
| The panel itself | 2240×1080 | 2.0741 |

A 2240×1080 H.264 clip pushed to `/sdcard/pcMedia/` **displays black** — it is
accepted, no error is logged, and nothing plays. Confirmed on firmware 1.0.10
under a keepalive (`tests/video_matrix.py`); an earlier 1.0.7 observation said
the same but predates the keepalive fix and doesn't count on its own.

### The VPU is real, and H.264 is its weakest format

Reading only `media_codecs.xml` and `media_codecs_google_video.xml` suggests
there is no hardware video codec on this board. **That conclusion is wrong
twice over**, and it is an easy one to reach: the codec configuration is spread
across seven files, and `media_codecs_c2_base.xml` is the one that registers
Rockchip hardware codecs through Codec2. The limits it declares:

| Codec2 name | Type | Max size | Max block count |
| --- | --- | --- | --- |
| `c2.rk.avc.decoder` | `video/avc` | **1920×1088** | 8160 |
| `c2.rk.hevc.decoder` | `video/hevc` | **4096×2160** | 32768 |
| `c2.rk.vp9.decoder` | `video/x-vnd.on2.vp9` | **4096×2160** | — |
| `c2.rk.avc.encoder` | `video/avc` | **1920×1088** | — |

That asymmetry is the whole story of this section, and it is a common Rockchip
VPU shape: **H.264 is a 1080p-class capability while HEVC and VP9 are
4K-class.** The panel is 2240 px wide. H.264 runs out; HEVC has room to spare.

It also gives `scrcpy` a much better explanation than "there is no hardware
encoder". `c2.rk.avc.encoder` maxes at **1920×1088**, and the display it is being
asked to encode is **2240×1080** — wider than the hardware encoder accepts. That
is why the default encoder fails and forcing a software one works. Nothing to do
with there being no hardware; the hardware just can't encode a frame this wide
in H.264.

### Playback goes through rockit, not MediaCodec

`adb logcat` during a successful playback
([`captures/video-decode.log`](captures/video-decode.log)):

```
D rockit : RTConfigXML {verifyCodecTag:221} verify codec Tag:: codecName = avc1
I h264d_api: is_avcC=1
D rockit : video chain: chain(demux/avcodec/videosink),
           codec(name=rk_mpp/bitrate=2201k/1920x926x@30.00)
```

**`rockit`** is Rockchip's own media framework and **`rk_mpp`** is the Media
Process Platform — it talks to the VPU directly rather than through Codec2. So
the Codec2 declarations above describe the *hardware's* capability, but rockit
is not bound by the exact numbers in them:

| Clip | Blocks | vs declared 8160 | Result |
| --- | --- | --- | --- |
| 1920×1080 | 8160 | exactly at the limit | ✅ |
| 2048×1080 | 8704 | **over** | ✅ |
| 2240×1080 | 9520 | **over** | ❌ |

2048×1080 exceeds the declared block count and plays anyway, so the XML is not
being enforced literally — but the hardware does run out, somewhere between
2048 and 2240 px wide. The declaration tells you the *intent*: 1080p-class
H.264 decode.

### Why a too-large clip black-screens instead of erroring

The same log, for the clip that fails:

```
ffmpeg: Video: h264 (avc1), yuv420p(tv, bt709, progressive), 2240x1080 ...
D rockit : RTConfigMeta {verifyCodecTag:154} verify codec Tag:: codecName = avc1
   ... repeats every ~80 ms, forever
```

| | 1920×926 (plays) | 2240×1080 (black) |
| --- | --- | --- |
| Resolver | `RTConfigXML :221` | **`RTConfigMeta :154`** |
| Reaches `h264d_api` | ✅ `is_avcC=1` | ❌ never |
| Builds a video chain | ✅ `codec(name=rk_mpp/…)` | ❌ never |
| Outcome | plays | retries indefinitely |

A clip within the VPU's reach is resolved by `RTConfigXML` and gets an `rk_mpp`
decoder. One beyond it falls through to `RTConfigMeta`, never acquires a
decoder, and loops — no error, no software fallback. That is exactly why the
panel sits black with nothing logged at the Android level.

### ✅ Native resolution works — in HEVC

Confirmed on firmware 1.0.10. **2240×1080 H.265 plays full-screen**, where the
identical frame in H.264 black-screens.

| Clip | Codec | Result |
| --- | --- | --- |
| 2240×1080 | H.265 (`hvc1`) | ✅ plays |
| 1920×1080 | H.265 (`hvc1`) | ✅ plays |
| 2240×1080 | H.264 | ❌ black |

So the limit was never the panel, the compositor, the session, the profile, the
level or the frame size. **It was the codec.** `c2.rk.avc.decoder` declares
1920×1088 and `c2.rk.hevc.decoder` declares 4096×2160, and those two numbers
predicted the outcome exactly.

The correct statement is therefore: *native-resolution **H.264** does not play on
this panel.* Video in general is fine at the panel's full 2240×1080 — encode it
as HEVC.

`-tag:v hvc1` is not optional. `verifyCodecTag` checks the fourcc and `hvc1` is
what rockit and Android expect; `hev1` is the other legal tag and is much less
widely accepted.

VP9 is also declared to 4096×2160 and is the untested third option, if you want
a royalty-free codec. **Not in a `.webm`, though.** The extension dispatch
(below) runs before anything looks at the codec: `.mp4` goes to `VideoView`,
`.gif` to Fresco, and *anything else* to Glide as a still image. A `.webm`
would be handed to an image loader and never reach a decoder at all. VP9 does
have a path — VP9-in-MP4, sample entry `vp09`, a legal combination that ffmpeg
writes and the `.mp4` extension gets to `VideoView`:

```bash
ffmpeg -i in.mp4 -vf "scale=2240:1080:force_original_aspect_ratio=increase:flags=lanczos,setsar=1,crop=2240:1080" \
  -c:v libvpx-vp9 -tag:v vp09 -pix_fmt yuv420p \
  -crf 30 -b:v 0 -maxrate 8M -bufsize 16M -movflags +faststart -an out.mp4
```

That relocates the uncertainty rather than removing it. The container question
is solved; the open one is whether rockit's `verifyCodecTag` accepts `vp09`
the way it accepts `avc1` and `hvc1`. If it doesn't, the clip falls through to
`RTConfigMeta` exactly like an oversized H.264 one and black-screens.
`tests/video_matrix.py --vp9-test` builds and runs it.

### Encode targets

**Full screen at the panel's native resolution — use HEVC:**

```bash
ffmpeg -i in.mp4 -vf "scale=2240:1080:force_original_aspect_ratio=increase:flags=lanczos,setsar=1,crop=2240:1080" \
  -c:v libx265 -tag:v hvc1 -pix_fmt yuv420p \
  -crf 24 -maxrate 8M -bufsize 16M -preset slow -movflags +faststart -an out.mp4
```

**If you need H.264** — older tooling, or you want to match ASUS's own clips —
stay at or under 1920 px wide:

```bash
ffmpeg -i in.mp4 -vf "scale=1920:926:force_original_aspect_ratio=increase:flags=lanczos,setsar=1,crop=1920:926" \
  -c:v libx264 -pix_fmt yuv420p \
  -crf 20 -maxrate 8M -bufsize 16M -preset slow -movflags +faststart -an out.mp4
```

**Split screen** — both zones are inside the H.264 limit, so either codec works:

```
zone 1 (main face)   scale/crop 1606:1080
zone 2 (side strip)  scale/crop  634:1080
```

**Don't pin `-level`.** It is harmless at 1920×926 and wrong above it: a frame
over 8192 macroblocks exceeds Level 4.0, so x264 would write a level the stream
violates. Leaving it out lets x264 pick one the stream satisfies. This is
tidiness, not a fix — a 2240×1080 H.264 clip with an honest level still doesn't
play, because the limit is the AVC decoder rather than the header.

**`-profile` doesn't matter.** Baseline and High play identically at every size
tested, including failing identically at 2240×1080, so there is no reason to pay
Baseline's compression penalty. The `ProfileBaseline` declaration in
`media_codecs.xml` is not enforced on the playback path.

**Keep the bitrate capped.** Decode is hardware (`rk_mpp`), but the rest of the
pipeline still has to keep up; an uncapped CRF encode can spike and give you
stutter rather than a clean failure. `-maxrate 8M` is there for that. Info Hub's own transcodes run
~95 MB for a single clip, so it clearly isn't optimising for this either.

**Stills are different.** Info Hub copies `.png` / `.jpg` through verbatim at
whatever size you give it — `Glide` scales at render time, so there's no
transcode and no resolution constraint. Only video goes through `VideoView`,
which is the fussy path.

`setLayout1Path` then dispatches on extension:

| Extension | Player | Advances when |
| --- | --- | --- |
| `.mp4` | VideoView | clip ends |
| `.gif` | Fresco, one-shot | gif ends |
| anything else | Glide still image | after a hardcoded **7000 ms** |

Missing files are skipped (it just posts "play next"). Playlists can mix all
three freely.

### You can watch the panel scan

On content with abrupt full-frame brightness changes — a lightning strike, a cut
to white, a hard flash — the change does not appear everywhere at once. It
**sweeps across the screen horizontally**, visibly, as a wavefront.

This is not an encoding artefact and not a decode problem. It is the panel's own
scanout, and it is visible here for two reasons that compound:

* **The panel is physically portrait**, 1080×2240, rotated 90° into landscape by
  SurfaceFlinger. A DSI panel refreshes its own rows in sequence, top to bottom
  *in panel space* — and after a 90° rotation that axis lands on the
  **horizontal** axis of what you're looking at. So the scan you'd normally see
  as a top-to-bottom roll appears as left-to-right instead.
* **It's an OLED.** Pixels change state essentially instantly. On an LCD the
  slow pixel response smears the wavefront into invisibility; here there is
  nothing to hide it.

At 60 Hz a full scanout takes **16.7 ms**, which is inside the range the eye
resolves for a sudden full-field luminance change.

Nothing can be done about it from the protocol side — it is how the display
works. It is worth knowing mainly so you don't go looking for a bug in your
encode. It does argue against one kind of content: clips with hard cuts to white
or strobing will always look slightly wrong on this panel, while gradual
transitions will not.

> **It is also free confirmation that the panel really is a rotated portrait
> display**, without needing adb. And it comes with its own falsification test:
> the sweep direction is a property of the hardware, not the content, so it
> should run the *same way every time* regardless of what is playing. If you
> ever see it sweep the other way, this explanation is wrong.

### Burn-in protection: your widgets vanish for 2 seconds every ~5 minutes

The panel is OLED and the six widget slots are static text in fixed positions,
which is the textbook burn-in risk. The launcher's mitigation is a small state
machine that runs on the **media-advance** handler — the same code path that
picks the next item in a playlist.

Two flags, one timer. In pseudocode — a description of the control flow, not a
quote:

```
on media advance:
    if not (nextProtectMode1 and protectBaseTimeout1):
        show the six widget slots
        nextProtectMode1 = true
        play the next media item
        return
    # both flags set -> protect mode
    nextProtectMode1 = protectBaseTimeout1 = false
    cancel and re-arm the 5-minute timer  (message 118, 300 000 ms)
    hide the six widget slots
    switch zone 1 to the protect video     (Screensaver.mp4)
    schedule "advance again" in 2 000 ms   (message 102)
```

`isNextProtectMode1` is set on every ordinary advance, so after the first one it
is effectively always true. `isProtectBaseTimeout1` is set by message **118**,
the 300 000 ms timer. Protect mode therefore fires on **the first media advance
after the five-minute timer expires**, and lasts exactly **2 seconds** before
message 102 re-enters the same handler with both flags cleared and everything
comes back.

Three consequences worth knowing before you file a bug against your own client:

* **Your widgets disappearing for two seconds is normal.** All six slots blank,
  the panel switches to `Screensaver.mp4`, and then everything returns. Nothing
  in the protocol caused it and nothing you send can suppress it — there is no
  resource for this. It is entirely internal to the launcher.
* **Long media doesn't reduce interruptions — it reduces *protection*.**
  `MSG_HANDEL_MEDIA` is only posted from `onCompletion` and from the 7 s
  still-image timer, so the protect branch cannot fire while something is
  playing. It isn't being suppressed mid-clip; the check simply isn't running.

  | Content | Advance every | Protect fires |
  | --- | --- | --- |
  | still image | 7 s | ~5 min |
  | 12 s clip | 12 s | ~5 min |
  | 10 min clip | 10 min | ~10 min |
  | 30 min clip | 30 min | ~30 min |

  The widget text is static no matter what plays underneath it, so clip length
  has **no effect on the burn-in risk and an inverse effect on the mitigation**.
  A long clip means the same static text sits on an OLED for longer without a
  break.

  **That is the opposite of a feature.** Burn-in protection here is throttled by
  exactly the content most likely to cause burn-in, because both are keyed to
  the same boundary. If you care about the panel, prefer shorter items or a
  playlist; a single 30-minute clip gives the six text slots half an hour of
  uninterrupted static display at a time.
* **It is zone 1 only.** `setLayout1Path`, `isNextProtectMode1`,
  `isProtectBaseTimeout1` — all suffixed `1`, and `standby_video` exists only
  inside `home_layout1` (see §8). In split mode the side strip does not get a
  screensaver.

This is also the same `protectVPath` that `displayInSleep` switches to, which is
why setting that resource puts `Screensaver.mp4` on screen.

#### Protect mode shows two seconds of an 11.9-second clip

The protect branch plays `Screensaver.mp4` and then posts message 102 again
after **2000 ms**, which switches straight back to your media. The clip is
**11.9 seconds long**, so protect mode only ever shows its first ~2 seconds
— every five minutes, the same opening moment, cut off.

There is nothing hidden in the rest of it. `Screensaver.mp4` is not unique
content — it plays the same video as one of the `RYUO_IV_HW_Info_*.mp4` presets (see
below), all of which are viewable in Info Hub, and toggling `displayInSleep`
(§4) puts the file itself on screen. It's just an odd choice: an 18 MB file for a
two-second cutaway.

### The four media locations, and what standby actually does

```
sdcard/pcMedia/                        your uploads
sdcard/pcMediaPreset/                  ASUS presets (RYUO_IV_HW_Info_01..05.mp4)
/system/media/anim/                    rain.webp, vapor.webp  (overlay effects)
/system/media/video/                   standby.mp4, Screensaver{,_left,_right}.mp4
```

`/system` is mounted read-only. There is no dm-verity on this build (see §11),
so a remount is not off the table the way it would be on a phone — but nothing
here needs it, and there is no unbrick path if you break something. Don't.

There are **two separate video views**, which produces a genuinely misleading
symptom if you don't know:

| View | Plays | When |
| --- | --- | --- |
| `standby_video` | `standby.mp4` | no `ScreenConfig` has been received, or the session lapsed (§10) |
| `standby_video` | `Screensaver.mp4` | burn-in protection kicks in |
| `main_video1` / `main_video2` | your `media[]` | normal operation |

`Screensaver.mp4` is **burn-in protection**, not an idle animation — the field
is called `protectVPath`, and it's driven by `sendEmptyMessageDelayed(118,
300000L)` five-minute timers armed in `screenConfigChange()`. It's an AMOLED;
that's what those are for.

The trap: `Screensaver.mp4` is not its own clip — on **firmware 1.0.7** it plays
the same content as `RYUO_IV_HW_Info_02.mp4`, one of the stock presets (same
video by eye; the md5 sums differ, so it's a re-encode or a different cut of
the same clip rather than a copy — which changes nothing about how it looks). ASUS moves these around between releases — on **1.0.10**
`standby.mp4`, which was a unique clip on 1.0.7, plays the same content as
`RYUO_IV_HW_Info_05.mp4`; see §10b. Check your own unit
rather than trusting either statement. If the preset the screensaver copies
happens to be your selected media, "the screensaver is playing" and "my
configured video is playing" look exactly the same while being two different
views on two different code paths. Change your media to something else before
concluding anything about standby behaviour.

`adb reboot` clears the held config, which makes it a clean reset to the
`standby.mp4` state for testing.

`Screensaver_left.mp4` and `Screensaver_right.mp4` are declared as
`protectVLPath` / `protectVRPath` and **never referenced anywhere in the app**.
Dead fields; ASUS ships ~25 MB of unused video on every unit.

---

## 8. Split screen

`screenMode` is `"Full Screen"` for the single-zone path. **Any other string** takes the split branch — the exact value Info Hub sends is `"Screen Splitting"`.

In the split branch, three fields become two-element lists, one per zone:

```jsonc
{
  "screenMode": "Screen Splitting",
  "playMode": ["Single", "Cycle"],
  "media": [["main.mp4"], ["strip.png"]],
  "settings": [ {/* zone 1 */}, {/* zone 2 */} ],
  "sysinfoDisplay": ["...", "...", "...", "...", "...", "..."]   // stays flat!
}
```

`sysinfoDisplay` does **not** split — it stays a flat 6-slot array, 3 slots per zone.

Captured from Info Hub the moment the user switched to Split — the raw line is
in [`captures/infohub-split-capture.log`](captures/infohub-split-capture.log):

```
--screenConfigChange--config:ScreenConfig{Type='null', id='Customization',
screenMode='Screen Splitting', ratio='null', playMode=[Single, Single],
media=[[a.png], [b.png]], sysinfoDisplay=[CPU Temperature, GPU Temperature, , , , ],
settings=[{titleColor=#2ee525, ...}, {titleColor=#2ee525, ...}], timeZone='null'}
```

Note `timeZone='null'` — Info Hub omits it on subsequent pushes once it has been
set once. Sending it every time (as `ryuo_send.py` does) is harmless.

### Geometry

The panel is **2240×1080** (physically 1080×2240 portrait, rotated 90° by SurfaceFlinger). Split tiles it as:

| Zone | Size | Aspect |
| --- | --- | --- |
| 1 — main face | **1606×1080** | 1.4870 |
| 2 — strip past the bend | **634×1080** | 0.5870 |

✅ **Measured on a framebuffer capture, and it matches the layout resource
exactly.** `adb exec-out screencap -p` during a live split session — solid red
in zone 1, solid green in zone 2 — puts the colour transition at **x = 1606** on
every row sampled, in a 2240×1080 image. Zone 2 is the remaining 634 px.
Numbers in [`captures/split-geometry.md`](captures/split-geometry.md).

The layout resource says the same thing. `main_parent` is a horizontal
`LinearLayout` holding two `RelativeLayout` children: `home_layout1` with a
width of `0dip` and `layout_weight` 1.0, and `home_layout2` with a fixed width
of `634px` (and `visibility="gone"` until split mode turns it on).

**Zone 2 is a hardcoded 634 px. Zone 1 is `layout_weight=1.0`** — it isn't a
percentage at all, it's simply whatever is left: 2240 − 634 = 1606. There is no
divider view between them.

### ASUS's crop tool and ASUS's layout disagree by 6 px

Info Hub's crop tool enforces aspect ratios of **1.4819** and **0.5925** — its
two crop boxes measure 1024×691 and 1204×2032 in the UI — which is a clean
**1600 / 640** split of a 1080-high panel (1.4815 and 0.5926). The layout
renders **1606 / 634** (1.4870 and 0.5870). Those are not the same split, and
the crop tool's numbers are the ones you can see from the outside, so they are
the easy thing to write down and get wrong.

Nobody at ASUS appears to have noticed, and the reason is the next line of the
layout: the still-image view for zone 1, `main_img1`, is declared with
`scaleType` **1**.

`scaleType=1` is **FIT_XY** — stretch to fill, aspect ratio discarded. Still
images are squashed into the zone whatever their dimensions, so a 6 px error is
invisible. It also means **you don't need to match the zone aspect**; you need
to match it to avoid *distortion*, which is a different thing. Get it wrong by a
lot and your image is visibly stretched, with no letterboxing to warn you.

The animated-WebP view uses `scaleType=6` (CENTER_CROP) instead, so animated
content crops rather than stretches. Two different behaviours in the same zone
depending on what you put in it.

> The FIT_XY/CENTER_CROP split also explains §5's `ratio` results: `1:1` and
> `4:3` visibly rescale a still because the `ImageView` will stretch to
> whatever box it's given, while the same ratios leave video alone. Nothing
> black-screens — an earlier reading of this as "ratio breaks video" was a
> media-loading artefact, now retracted in §5.

### Only zone 1 gets a standby video

`standby_video` lives inside `home_layout1` only — there is no second standby
view. The burn-in state machine agrees: every flag and setter in it is suffixed
`1` (`isNextProtectMode1`, `setLayout1Path`), so in split mode the side strip
never gets a screensaver. See §7 for how that cycle works.

That is very likely why `Screensaver_left.mp4` and `Screensaver_right.mp4` exist
as separate files, and why the path looks half-wired: somebody intended to
protect both zones and only one got built.

---

## 9. `POST preset` — the live-update channel

```jsonc
{
  "id": "Customization",
  "sysinfoDisplay": ["CPU Temperature", "GPU Temperature", "Date&Time", "", "", ""],
  "settings": {
    "titleColor": "#00FF9C",
    "contentColor": "#FFFFFF",
    "filter": { "value": null, "opacity": 100 },
    "badges": []
  }
}
```

This is `MainActivity` case **114**, and it's the useful one. It calls `setSysinfoDisplay` / `setSettings`, repaints the text views, and returns. It does **not** hide `mainParent` and does **not** tear down the video player — so you can hammer it at 10+ fps for colour animation while media keeps playing underneath.

That's the whole trick behind the rainbow and thermal modes in `ryuo_send.py`.

### `filter.value` — an overlay Info Hub never exposes, with no selection

`filter.value` is `null` in every captured frame, and `/system/media/anim/`
contains exactly two files, `rain.webp` and `vapor.webp`. Those looked like the
obvious enum values. **They are not.** Tested on firmware 1.0.7:

| `filter.value` | Overlay |
| --- | --- |
| `"Rain"` | ✅ drawn |
| `"VAPOR"` | ✅ drawn — identical |
| `"banana"` | ✅ drawn — identical |
| `"xyzzy"` | ✅ drawn — identical |
| `""` | none |
| `null` | none |

**Any non-empty string draws the same overlay.** Empty string and null draw
nothing. So this is a `value != null && !value.isEmpty()` check with a single
hardcoded effect — not an enum, and `rain` and `vapor` are not the API's
vocabulary. Whatever selects between the two `.webp` assets, it isn't this
field.

So the honest statement is: **you can turn one overlay on, and you cannot choose
which.** That is still a feature ASUS's software gives you no way to reach.

It also isn't a good effect, which may be why it's unreachable. It renders as
large rectangles travelling **left to right** — the wrong axis for anything
called "rain".

> **`"rain"` and `"vapor"` looked like the valid strings** — two asset
> filenames, plus a probe run in which both drew an overlay. That conclusion was
> wrong in the most ordinary way available: the hypothesis was only ever tested
> against values that confirm it. Adding two nonsense strings as a control took
> thirty seconds and overturned it immediately. The asset filenames are real;
> the inference from them was not.

(`filter.opacity` is a float internally: the app's `toString` prints `100.0`.)

`badges` is **dead** — a `List<String>` on `PmSetting` with a getter, a setter
and no reader anywhere in the app. Three payload shapes were tried on hardware
first, all ACKed, none rendered anything; reading the source afterwards
explained why. See the dead-code section in §4.

---

## 10. `POST all` — telemetry

Sent roughly once per second. This is a **real frame** from the logcat capture,
exactly as Info Hub sent it (line-wrapped for readability; the `memory` and
`disk` totals are the sanitised placeholders from `captures/`, everything else
is verbatim):

```json
{"network":{"upload":0,"download":2},
 "memory":{"total":32768,"used":16384,"load":50,"temperature":0,"speed":3000},
 "cpu":{"load":7,"temperature":36,"temperaturePackage":46,"speedAverage":5325,
        "power":48,"voltage":1.147,"usage":6},
 "gpu":{"hasDedicated":true,"load":9,"temperature":49,"fan":0,"speed":2640,
        "power":87,"voltage":0.965},
 "disk":{"total":1000,"used":500,"load":50,"activity":0,"temperature":0,
         "readSpeed":0,"writeSpeed":0},
 "fans":[{"onBoard":true,"name":"CPU","value":2119},
         {"onBoard":true,"name":"AIO Pump","value":3229},
         {"onBoard":true,"name":"Chassis 5","value":546},
         {"onBoard":true,"name":"Chassis4","value":513}],
 "motherboard":{"temperature":31,"chipsetTemperature":52},
 "timestamp":1788799762208}
```

Note `gpu` has no `usage` key even though `cpu` does, and `memory.temperature`
and the disk speed fields were flat zero throughout — Info Hub sends the keys
whether or not it has a value for them. Send them as `0` rather than omitting
them.

Units are the part that bites:

| Field | Unit |
| --- | --- |
| `memory.total` / `used` | **megabytes** |
| `disk.total` / `used` | **gigabytes** |
| `cpu.speedAverage` | MHz |
| `network.upload` / `download` | KB/s |
| `timestamp` | milliseconds |
| all temperatures | **always Celsius** — the device converts for display based on the `temperature` resource |

Sending memory in bytes or GB is the single easiest way to get nonsense on
screen.

### Fan names are load-bearing

There is no fixed set of fan widget items. The item string is built at runtime
as `"Fan Speed " + fans[].name`, so **the names in your telemetry decide what
item strings exist** — see below for the mechanism and what else it lets you do.

For the four fans Info Hub knows about, that means the working strings are
`Fan Speed CPU`, `Fan Speed AIO Pump`, `Fan Speed Chassis 5` and
`Fan Speed Chassis4`, matching the `CPU` / `AIO Pump` / `Chassis 5` /
`Chassis4` entries in the capture.

Note that ASUS's own naming is inconsistent — `Chassis 5` with a space,
`Chassis4` without — and matching is literal, so reproduce the oddity rather
than tidying it up. If you tidy the telemetry name, the item string has to
change to match, or the slot renders a label with a stale number under it.

### The widget item list, from the renderer

**All sixteen items below render on hardware** — label and value both — tested
one batch of six at a time on firmware 1.0.10. This table is no longer a
reading of the source; it is a list of things that have been seen on a panel.

`sysinfoDisplay` only carries **label strings**. Two maps in `HomeUI` turn each
one into something on screen, and **an item only works if it is in both**:

* `subTitle` — a `HashMap<String,String>` from item name to the label drawn.
  `showInfo()` reads it.
* the `setInfoValue(item, value, unit)` calls in `onRefreshUI()` — item name to
  the value drawn.

An item in `subTitle` only gives you a label with no value. An item with a value
handler but no `subTitle` entry gives you a value under a blank label. That
second failure mode is real and observable, which makes "the widgets didn't
change" and "the labels vanished but the numbers stayed" two different bugs.

| Item string | Source field | Unit |
| --- | --- | --- |
| `CPU Load` | `cpu.load` | % |
| `CPU Usage` | `cpu.usage` | % |
| `CPU Temperature` | `cpu.temperature` | °C/°F |
| `CPU Speed Average` | `cpu.speedAverage` | MHZ |
| `CPU Voltage` | `cpu.voltage` | V |
| `GPU Load` | `gpu.load` | % |
| `GPU Usage` | ⚠️ **`gpu.load`** | % |
| `GPU Temperature` | `gpu.temperature` | °C/°F |
| `GPU Speed` | `gpu.speed` | MHZ |
| `GPU Power` | `gpu.power` | ⚠️ **°C/°F** |
| `GPU Voltage` | `gpu.voltage` | V |
| `Memory Utilization` | `memory.load` | % |
| `Memory Frequency` | `memory.speed` | MHZ |
| `Hard Disk Temperature` | `disk.temperature` | °C/°F |
| `Motherboard Temperature` | `motherboard.temperature` | °C/°F |
| `Date&Time` | clock | — |
| `Fan Speed <name>` | `fans[].value` | RPM |

> **`Fan CPU`, `Fan AIO Pump`, `Fan Chassis4` and `Fan Chassis 5` are not item
> strings** — though the *names* in them are right. Info Hub's picker groups
> its tiles under a **Fan Speed** heading with the labels `CPU`, `AIO Pump`,
> `Chassis 5` and `Chassis4`, and an earlier pass reconstructed the item
> strings by joining the heading to the label with the wrong word. The real
> prefix is `"Fan Speed "`, so the working strings are **`Fan Speed CPU`**,
> **`Fan Speed AIO Pump`**, **`Fan Speed Chassis 5`** and
> **`Fan Speed Chassis4`** — and they render whenever the host sends a
> matching `fans[].name`. They were never separate items at all; they are
> instances of the dynamic pattern below.
>
> `Hard Disk Temperature` was missing from the list entirely. The other twelve
> were correct.

`GPU Frequency`, `Date` and `Time` have value handlers but no `subTitle` entry,
so they render a number under a blank label. Half-implemented; don't use them.

### The session is a dead-man's switch

**`POST all` is not just telemetry. It is what keeps your configuration
alive.** Stop sending it and within ~10 seconds the screen drops to standby —
widgets gone, panel dimmed, `standby.mp4` playing — as if you had never
connected.

There is no timeout you can configure, no acknowledgement that it is about to
happen, and no error. The screen simply goes back to what it was.

This is the single most common way to waste an afternoon on this device,
because the symptom points somewhere else entirely:

* Push a config, look up at the panel, see your change, look back down. Fine.
* Push a config, stop to read something or type an answer, look up. Standby.

Same code, opposite result, and the variable is how long you spent looking away.
A harness that sends a config and then blocks on `input()` will report that
every single change failed, which is exactly what happened to `tests/probe.py`
across several runs before this was understood.

> **The diagnostic that gives it away: it works with Info Hub running.** Leave
> ASUS's app open in the background and your changes stick, because *it* is
> supplying the continuous `POST all`. Close it and the same commands stop
> working. If you are seeing that, this is why — and your telemetry is the part
> that isn't landing, not your config.
>
> It also explains the values. With Info Hub running you will see *real*
> numbers, because they are Info Hub's readings, not yours.

Practically: run the keepalive on a **background thread** from the moment you
connect, not inline between commands. `Link.start_keepalive()` in
`tests/probe.py` is a minimal version — one `POST all` per second, a lock
around the HID writes, and a daemon thread so Ctrl-C still works.

And make the values you send **change every tick**. A slot with no matching
telemetry keeps its previous number (see below), so a readout that is quietly
dead looks exactly like one that works. If the number is moving, the slot is
live.

### Slots are not cleared — a missing value leaves the old one on screen

The two maps behave independently, and neither clears anything.

`showInfo()` rewrites the **label** the moment a new `sysinfoDisplay` arrives.
`onRefreshUI()` only writes a **value** for items it finds in the current
`PcInfo`. If a slot's item has a label but no value source, the label changes
and the number under it **keeps whatever was there before**.

Observed on firmware 1.0.7: a slot set to `Fan Speed Coolant`, with no fan
named `Coolant` in the telemetry, displayed the label **Coolant** above the
CPU temperature left over from the previous configuration. `33C` under a label
that has nothing to do with temperature.

That is worth knowing for three reasons:

* **A stale number looks exactly like a working one.** There is no dash, no
  blank, no zero. Any readout you add is guilty until you have watched it
  change.
* It is the clearest demonstration of the two-map design. The label path
  succeeded and the value path never ran, and you can see both halves on the
  panel at once.
* If you push a config whose items don't match your telemetry, the screen will
  confidently show you last minute's data under this minute's headings.

Change something that should move and watch it move. That is the only check
that distinguishes a live slot from a fossilised one.

### The on-screen label is not the item string

`subTitle` maps each item to a **shortened** label, and the shortening is lossy.
Read off a framebuffer capture of a live session:

| Item string sent | Label drawn |
| --- | --- |
| `CPU Temperature` | `CPU` |
| `GPU Temperature` | `GPU` |
| `CPU Voltage` | `CPU` |
| `Fan Speed Chassis4` | `Chassis4` |
| `Fan Speed Chassis 5` | `Chassis 5` |

**`CPU Temperature` and `CPU Voltage` both draw `CPU`.** The unit disambiguates
them on screen — `32°C` versus `1.089V` — but the label does not, so you cannot
read a panel and recover which items are configured. When debugging a slot, go
by the unit, or configure one item at a time.

It is also why the `Fan Speed <name>` trick reads cleanly: the label is the part
after character 10, so a custom readout shows exactly the name you chose with no
prefix attached.

### `Fan Speed <name>` — arbitrary labelled readouts

The fan item is built at runtime, and that makes it the most useful thing in the
protocol. Two places in `HomeUI` do it, described rather than quoted:

* `onRefreshUI()` walks `fans[]` and, for each entry, sets the value for the
  item named `"Fan Speed "` + the entry's `name`, with the entry's `value` and
  the unit `RPM`.
* `showInfo()` checks whether an item string starts with `Fan Speed` and is
  longer than 10 characters; if so, the label it draws is the item string from
  character 10 onward.

The item string is `"Fan Speed " + whatever you put in fans[].name`, and the
on-screen label is **everything after character 10** — which is the name you
chose. You control the key and the label.

So any number you can measure on the host can be put on the panel under any
label you like:

```bash
python ryuo_send.py \
  --readout Coolant=3229 \
  --items "Fan Speed Coolant" "CPU Temperature" "Date&Time"
```

`--readout` injects `{"onBoard": true, "name": "Coolant", "value": 3229}` into
`fans[]`, and the panel draws **Coolant · 3229 RPM**.

✅ **Confirmed on firmware 1.0.10.** Three invented labels — `Coolant`,
`NAS Bay 3` and `Unread` — all rendered with their values and the unit `RPM`.
There is no validation of any kind on the name: if you can put a number next to
a string, the panel will show it.

The unit is always RPM, so it suits anything countable and lies about anything
else. Within that, this is the only route to a readout ASUS's software cannot
produce: pump RPM from a different header, a NAS temperature, unread emails,
build queue depth, days since the last incident.

### Info Hub exposes less than the renderer supports

Info Hub's widget picker offers six groups — Temperature, Fan Speed, Voltage,
Frequency, Usage, Others — and fourteen tiles:

| Group | Tiles | Item string |
| --- | --- | --- |
| Temperature | CPU · Motherboard · GPU | `CPU/Motherboard/GPU Temperature` |
| Fan Speed | CPU · AIO Pump · Chassis 5 · Chassis4 | `Fan Speed <name>` |
| Voltage | CPU · GPU | `CPU/GPU Voltage` |
| Frequency | CPU · GPU | `CPU Speed Average`, `GPU Speed` |
| Usage | CPU · GPU | `CPU Usage`, `GPU Usage` |
| Others | Date&Time | `Date&Time` |

The renderer supports more than that. **Items with no tile in ASUS's UI at
all:**

* **`GPU Power`** — watts, drawn from `gpu.power`
* **`Memory Utilization`** — `memory.load`
* **`Memory Frequency`** — `memory.speed`
* **`Hard Disk Temperature`** — `disk.temperature`
* **`CPU Load` / `GPU Load`** — the UI has one "Usage" tile per chip, while the
  renderer has *both* a Load and a Usage item for each. Which string the tile
  emits is unknown without a capture; select Usage in Info Hub and read the
  resulting `config` to find out. (For the GPU it makes no difference — see
  bug 2 below.)

Plus `Fan Speed <anything>`, which has no UI representation beyond the four
fan headers the app happens to know about.

✅ **Confirmed on firmware 1.0.10: all of them render.** `GPU Power`,
`Memory Utilization`, `Memory Frequency` and `Hard Disk Temperature` each drew a
label and a live value. They need nothing but the right string in
`sysinfoDisplay` and the matching field in your telemetry — ASUS ships the
hardware and the renderer and simply never gives you a way to pick them.

(`GPU Power` works, but see bug 1 below: its unit prints as °C.)

### Two bugs in the renderer, and one that isn't

Found by reading the renderer, then confirmed on a panel (firmware 1.0.10):

1. **`GPU Power` displays its unit as °C.** Power, in degrees. A copy-paste
   from the temperature branch. The value itself is correct — only the unit is
   wrong. ✅ confirmed on device
2. **`GPU Usage` reads `gpu.getLoad()`, not `getUsage()`.** `GPU Load` and
   `GPU Usage` render the identical number, while the CPU pair are genuinely
   different. ✅ confirmed on device
3. ~~**Voltage units render as a literal `2`.**~~ ❌ **Retracted — there is no
   bug here.** The decompiler renders the voltage unit as
   `ExifInterface.GPS_MEASUREMENT_INTERRUPTED`, and that constant's value is
   **`"V"`** — the EXIF GPS status tag uses `"A"` for in-progress and `"V"` for
   interrupted. The decompiler simply substituted a named constant that happens
   to equal the string literal `"V"`. The source says `"V"`, the panel shows
   `1.098V`, and it is correct.

   Worth keeping as a worked example of the failure mode: a decompiler
   artefact was read as evidence of a bug, and the check that would have
   caught it was looking up what the constant actually equals — about fifteen
   seconds of work, skipped because the name looked absurd enough to be
   self-evidently wrong.

---

## 10b. Firmware versions

Verified against **1.0.7 and 1.0.10**, and believed to hold for **1.0.3
through 1.0.10**.

That range is not an assumption — the on-device launcher's version string is
**identical across 1.0.3, 1.0.7 and 1.0.10**. Same launcher, same message
dispatch table, same protocol. The firmware updates changed things around it,
not it.

That prediction has now been tested rather than merely argued: the widget item
list, the arbitrary-readout mechanism, both renderer bugs and the full
brightness transfer function were all established on 1.0.7 and then re-measured
on 1.0.10 with identical results, down to individual backlight values.

Known differences between versions:

| | 1.0.3 | 1.0.7 | 1.0.10 |
| --- | --- | --- | --- |
| USB vendor id | `0B05` | `1C75` | `0B05` |
| USB product id | `1C76` | `1C76` | `1C76` |
| Product string | `HID Interface` | `HID Interface` | `ROG RYUO IV Standard` |
| `standby.mp4` | — | unique clip | same content as `RYUO_IV_HW_Info_05.mp4` |
| `Screensaver.mp4` | — | same content as `RYUO_IV_HW_Info_02.mp4` (by eye; md5 differs) | not checked |
| adb root | open | open | open |
| Launcher / protocol | same | same | same |

So an update can change the USB identity and swap media assets out from under
you while leaving every frame layout in this document intact. Pin your tooling
to the product id and to the protocol, not to the vendor id or to a file that
happens to be on the device.

> `standby.mp4` becoming a duplicate of a bundled preset is worth noting if you
> ever relied on it being distinctive — it is no longer a way to tell the
> standby path apart from normal playback by eye.

### Downgrades are blocked — by recovery, not by Info Hub

Info Hub has **no downgrade check**. Hand it an older official firmware file and
it accepts it, says nothing, and reboots the screen into recovery. Recovery is
what says no. Full transcript in
[`captures/recovery-downgrade.log`](captures/recovery-downgrade.log):

```
Verifying update package...
Update package verification took 3.6 s (result 0)
Installing update...
E3003: Can't install this package (Tue Sep  9 17:11:13 CST 2025)
       over newer build (Mon Dec 29 09:26:28 CST 2025).
ERROR: recovery: Error in @/cache/recovery/block.map (status 1)
Installation aborted.
```

**`result 0` means the signature was accepted.** The 1.0.3 package is signed
with the same `otacert` the 1.0.10 recovery trusts, and it would have installed
— the only thing that stopped it was AOSP's `ota_downgrade_check` comparing the
package's `post-timestamp` against the running build.

That assertion lives *inside* the signed package, so it cannot be edited without
breaking the signature that just passed. On the OTA path — `upgrade`, Info Hub,
recovery — rollback to an older firmware is therefore properly blocked, not
merely inconvenient. Nothing was written; the device is untouched.

That is the *OTA* path. The bootloader is unlocked (§11), so it is not the only
way bytes can reach the flash; it is the only one this document and this
repository touch.

Those two timestamps also date the releases: **1.0.3 was built 2025-09-09** and
**1.0.10 on 2025-12-29** (CST, consistent with a Chinese ODM).

#### The part that will cost somebody an evening

The device is left sitting in recovery, and the menu says:

```
Use volume up/down and power.
```

**There are no buttons.** It is a screen on a water block. Every entry in that
menu — including `Reboot system now` — is unreachable by hand, so the only way
out is:

```bash
adb reboot
```

Meanwhile **Info Hub hangs**. It sits waiting for a completion that is never
coming, with no timeout and no error. After the reboot it finally surfaces an
error dialog *with no message in it*.

So the full user experience of an accidental downgrade is: a cooler showing a
recovery screen that tells you to press buttons you don't have, a host app
frozen on a progress state forever, and then an empty error box. Nothing is
broken, and nothing tells you that.

The recovery menu itself is stock AOSP and worth knowing:

| Entry | Note |
| --- | --- |
| `Reboot system now` | what you want; `adb reboot` does it |
| `Reboot to bootloader` / `Enter fastboot` | ☠️ no published image for this board, no unbrick path |
| `Apply update from ADB` | `adb sideload`; same signature and timestamp checks apply |
| `Apply update from SD card` | there is no SD slot |
| `Wipe data/factory reset` | would take `/sdcard/pcMediaPreset/` with it |
| `Mount /system`, `View recovery logs`, `Run graphics test`, `Run locale test`, `Enter rescue`, `Power off` | stock |

`adb` is available in recovery — that is how you get out — which is also how
`Apply update from ADB` would be driven if you ever needed to apply an official
package without Info Hub.

> **Security is unchanged through 1.0.10.** `adb shell` still gives an
> unauthenticated root prompt. If you were hoping ASUS would quietly close that,
> three firmware releases say otherwise. The disclosure note at the end of §11
> explains why that is published at all.

### The build fingerprint

Recovery prints it, and it sharpens the security picture rather than softening
it:

```
rockchip/cm16/cm16
13/TQ3C.230805.001.B2/eng.server.20251229.092713
user/release-keys
```

* **`cm16`** is the board codename — the same `cm16` in the `cm16:/ #` root
  prompt `adb shell` drops you into.
* **Android 13**, AOSP base `TQ3C.230805.001` (August 2023).
* `eng.server.20251229...` is the build *incremental*. When nobody sets
  `BUILD_NUMBER`, AOSP's `version_defaults.mk` fills it in as
  `eng.$(USER).$(date +%Y%m%d.%H%M%S)` — so `eng.` is a literal prefix, `server`
  is the Unix username the build ran under, and there is no hostname in it. It
  does **not** mean an engineering build *variant*; it means the image was
  produced without a release build number, i.e. not by a pipeline that assigns
  one.
* **`user/release-keys`.** This is a production build type signed with release
  keys.

That last point matters. A `userdebug` or `eng` build shipping root `adb` would
be unremarkable — that is what those build types are *for*. This is a `user`
build with `release-keys` that nonetheless ships `ro.debuggable=1` and an
unauthenticated root `adb` shell, on a board whose verified-boot state is
**orange** — bootloader unlocked, no secure boot, no dm-verity, and the
RK3562's maskrom mode reachable. Those are choices made on top of a production
configuration, not a debug build that escaped. The one thing that *is* locked
down is the OTA path: `upgrade` hands a package to recovery, and recovery
checks the signature and the timestamp (§10b). Everything below that layer is
open.

## 11. Device-side notes

Things that are true about the board but aren't part of the protocol:

* **GPU is a Mali-G52**, and SurfaceFlinger composites at the full native
  2240×1080: `dumpsys SurfaceFlinger` shows three `texture_renderbuffer`
  entries of 9.23 MB each, which is exactly 2240 × 1080 × 4 bytes,
  triple-buffered. So the width limit on H.264 video is the AVC decoder's, not
  the compositor's or the GPU's — see §7.
* **The panel is OLED.** Confirmed in the driver, not inferred from looking at
  it — `dmesg` prints `[oled_backlight_probe][265]:in`. That retroactively
  justifies the whole burn-in protection system (`standby_video`, the
  screensaver assets, the aggressive idle behaviour), which otherwise looks
  like over-engineering for a small screen on a water block. It also explains
  capping the DSI brightness register at 3315 of a possible 4095: running an
  OLED at 81% costs a little peak brightness and buys back a lot of panel life.
* **`adb shell` gives an unauthenticated root prompt** (`cm16:/ #`). No key prompt, nothing.
* **`scrcpy` works, but not on defaults** — it connects and then delivers no
  frames, and the reason is a declared limit rather than a broken codec. The
  h264 encoders on this build are both capped under the panel's 2240 px width:
  `c2.rk.avc.encoder` at `max="1920x1088"` and `OMX.google.h264.encoder` at
  `max="1280x720"`. scrcpy's default encoder selection goes through
  `MediaCodecList`, finds nothing that can serve the display, and streams
  nothing. Naming the encoder explicitly switches scrcpy to
  `createByCodecName()`, which skips the capability check and hands the software
  encoder the frames anyway — software encoders generally cope well past their
  declared size. One flag, nothing else needed:
  `scrcpy --video-encoder OMX.google.h264.encoder`
  (older scrcpy spells it `--encoder`). The decode side of the same asymmetry is
  why native-resolution video has to be HEVC — see §7.
* **You cannot install APKs.** The bundled PackageInstaller ships *only* `.UninstallActivity`. `pm install` verifies, stages and commits the session fine, then hangs forever waiting on a confirmation callback whose activity doesn't exist. No timeout, no error. Custom launchers and third-party apps are simply off the table.
* **hwmon has nothing useful**: `soc_thermal` plus factory test stubs (`test_ac`, `test_battery`, `test_usb`). No pump, fan or coolant sensor readable on-device — that's why all cooler telemetry has to come from the host.
* The factory app (`com.baiyi.app.factorymode`) is Chinese-only, which is a nice confirmation of the Baiyi ODM origin.
* **The `upgrade` resource stages an update zip** handed to `RKUpdateService`,
  which verifies against the bundled `otacert` in recovery. That is the official
  way firmware gets on the device, and it is properly gated: a package needs
  ASUS's private key and a newer timestamp than what is running.

  It is also the *only* gated way. The bootloader is unlocked (verified-boot
  state `orange`), there is no secure boot, no dm-verity, and the SoC's maskrom
  mode is reachable — so on this board the OTA signature check protects the OTA
  path, not the device. A "persistent implant on a root-shell Android box on
  your bus" is not blocked by anything below Android; it is blocked by nobody
  having bothered. Worth thinking about for a minute. It is not a door you
  should be rattling for fun, and nothing in this repository goes near it.

  **Rollback protection exists, but only on the device.** Info Hub will accept
  an older official firmware file and start the update without complaint — there
  is no downgrade check on the host side at all. The screen reboots into
  recovery, and *recovery* is what refuses it:

  ```
  E3003: Can't install this package (<older build date>)
         over newer build (<newer build date>)
  ```

  That is the standard AOSP `ota_downgrade_check` timestamp assertion, comparing
  the package's `post-timestamp` against the running build. Nothing is written;
  the package is rejected before any partition is touched.

  Two things follow, and the second one is the one that will cost somebody a bad
  evening:

  * The only rollback protection in the chain is the last link. A host-side
    check would have caught this in Info Hub; instead the device catches it
    after committing to a reboot. The check *works* — combined with the
    `otacert` signature requirement, an older firmware cannot be pushed back on
    through Info Hub or `upgrade` — but it works at the point of most
    inconvenience, and only on that path (see above).
  * **A refused update leaves the cooler sitting in recovery**, not back in the
    app. The screen shows a recovery menu — including a *fastboot* entry — and
    there is no indication that everything is fine. It is: `adb reboot`, or the
    menu's "Reboot system now", and the device comes back untouched. Do not
    take the fastboot option to see what it does. There is no published
    firmware image for this board and no unbrick path.
* **MTP is not enabled on the gadget.** Media upload goes through the HID envelope's `FileName` / `FileSize` / `ContentRange` headers — or, much more easily, `adb push` to `/sdcard/pcMedia/`.

### Disclosure

This document states in public that the screen ships with an unauthenticated
root `adb` shell and `ro.debuggable=1` on a `user/release-keys` build, with an
unlocked bootloader (verified-boot state `orange`), no secure boot, no dm-verity
and a reachable maskrom mode. Why that is published rather than reported
quietly:

* **It is the shipped configuration, not a discovered exploit.** Nothing here
  bypasses a protection; every unit sold has behaved this way on every firmware
  from 1.0.3 to 1.0.10, and anyone who plugs the cooler in and runs
  `adb devices` finds it in under a minute.
* **It needs access to the USB bus.** The device has no network interface of
  any kind, so the only way to reach it is physically, or as code already
  running on the host it is plugged into. Someone with either of those has
  bigger things to do with it than the water block. What the open boot chain
  changes is *persistence* — a compromised host could, in principle, leave
  something on the cooler that survives reinstalling the host — and that is a
  worse property than "root shell", which is why it is stated plainly here
  rather than tucked into a footnote.
* **Nothing in this repository lowers the bar further.** The official firmware
  path is signature-checked in recovery with rollback protection (§10b);
  `upgrade` is deliberately excluded from every tool and probe here, and
  nothing here touches the bootloader, fastboot or maskrom. What is published
  is a description of a USB HID protocol and an observation about a default
  setting.

As of publication this has not been raised with ASUS through a vulnerability
process, because — for the reasons above — it doesn't read as one. If ASUS or
Baiyi disagree, or if a later firmware closes the shell, the contact address
is on foxpodz.de and this section will be updated.

---

## 12. Writing your own client

The whole protocol is in `ryuo_proto.py` — framing, checksum, stuffing, and every payload builder — with no I/O in it. Roughly:

1. Open the hidraw node for product id `1C76` (any vendor id) interface 0.
2. Build a frame: JSON payload → HTTP-ish body → `encode()` → pad to 1024.
3. Write it in 1024-byte chunks with a report-ID byte in front.
4. Read 1024-byte reports until you've seen two `0x5A`s, slice between them, unstuff, verify the checksum.
5. Send `POST config` once. Wait ~1.6 s.
6. Loop `POST all` every second, forever, or the screen goes back to stock.
   **Run this on a background thread, not between commands** — if your code
   blocks on I/O or user input, the session lapses and everything you set
   reverts. See §10's dead-man's-switch note; this is the single most common
   way to lose an afternoon here.
7. `POST preset` whenever you want colours or widgets to change without restarting the media.
8. `POST disconn` on the way out.

---

## Licence

This document is licensed under the [GNU GPL v3 or later](LICENSE), like the
rest of this repository — share it, quote it, translate it, build on it, just
credit **FoxPodZ (foxpodz.de)**, keep derivatives under the same licence, and keep
the attribution.

The protocol described here is not mine and is not copyrightable: it's a
description of how a device built by ASUS and Baiyi behaves, written down for
interoperability. Reimplement it freely, in any language, under any licence.
That is entirely the point of this file existing.
