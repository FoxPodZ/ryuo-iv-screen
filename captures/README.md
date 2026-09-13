<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Captures

Raw evidence, not documentation. Everything in [`PROTOCOL.md`](../PROTOCOL.md)
is checked against what's in here — if the two ever disagree, the capture wins.

| File | What it is |
| --- | --- |
| `infohub-capture.log` | `adb logcat` on the cooler while genuine ASUS Info Hub drove it. Covers `POST config` on connect and the `POST all` telemetry loop. |
| `infohub-split-capture.log` | The moment Info Hub was switched to Screen Splitting. Evidence for §8 — the exact `screenMode` string, and the three fields that become two-element lists. |
| `split-geometry.md` | Framebuffer measurement of the split-screen zone widths — 1606 + 634, confirming the layout resource against a real capture. |
| `video-decode.log` | `logcat` of one clip playing and one black-screening. Shows playback going through rockit/`rk_mpp` rather than MediaCodec, and the `RTConfigXML` vs `RTConfigMeta` split that separates the two. The cause turned out to be codec, not size: H.264 decode caps near 1920 wide while HEVC reaches 4096. |
| `recovery-downgrade.log` | Android recovery refusing an official 1.0.3 package on a 1.0.10 device. Has the build fingerprint, the full recovery menu, and the `result 0` line showing the signature passed and only the timestamp blocked it. |

Sanitised: the capturing host's CPU/GPU model strings and RAM/disk sizes are
replaced with placeholders. Field names, nesting, types, units, ordering and
timing are exactly as captured.

## Adding one

`PROTOCOL.md` marks a lot of things 📖 (read from source, never sent) and ⚠️
(name only). Most of those need exactly one capture to get promoted to ✅. If
you have the hardware:

```bash
adb logcat -s HomeUI:* MsgReceiverManager:* SerialMsgReceiverHandler:* *:D \
  | grep -iE "STATE_POST|screenConfigChange|refreshShowData|VideoLog"
```

Toggle the thing you're curious about in Info Hub while that's running, then
open an issue with the log. **Check it before you post** — strip your CPU/GPU
model strings, hostnames and anything else you didn't mean to share.

`tests/probe.py` automates the other direction: instead of watching what Info
Hub sends, it sends things itself and asks you what the screen did.

## What's still open

Most of what this folder was collected to answer has been answered. What's left:

* **VP9 at native resolution.** `c2.rk.vp9.decoder` is declared to 4096×2160,
  same as HEVC, and HEVC works at 2240×1080. Never tried — and it has to be
  VP9-in-MP4 (`vp09`), because a `.webm` never reaches a decoder: the launcher
  dispatches on extension and sends anything that isn't `.mp4`/`.gif` to the
  still-image loader. The open question is whether rockit's `verifyCodecTag`
  accepts `vp09`. `tests/video_matrix.py --vp9-test` builds the clip.
* **The exact H.264 width cutoff.** 2048×1080 plays, 2240×1080 doesn't. The
  boundary between them has not been bisected — `tests/video_matrix.py
  --width-test` builds 2080 / 2112 / 2176 for it. Curiosity now rather than a
  blocker, since HEVC covers the use case.
* **`ScreenConfig.Type`.** `null` in every captured frame, never referenced
  anywhere useful in the app. No lead at all.
* **`power` restore event.** `shutdown` dims the panel — that's settled. What
  brings it back is not: the run that found it re-pushed a full config
  afterwards, and `config` carries `brightness`, so the restore could have been
  an event or the config. `tests/probe.py --only power_events` holds the config
  back until each candidate event has had its turn (see PROTOCOL.md §4).
* **`waterBlockScreenId`.** Takes a `ScreenConfig` and has never been sent.
* **`fanLCD` / `fanLCDSet`.** Sent, ACKed, no observed effect — but the tester's
  case fans made an audible result impossible to judge. Needs someone with a
  quiet machine, or a logcat approach.
* **Load vs Usage.** Info Hub's picker has one "Usage" tile per chip while the
  renderer has both a `CPU Load` and a `CPU Usage` item. Which string the tile
  emits would take one capture: tick Usage in Info Hub with logcat running.
* **AMD GPU telemetry.** `ryuo_send.py` reads NVIDIA only, via `nvidia-smi`.
  An `amdgpu`/sysfs path would need someone with the hardware.
