#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 FoxPodZ (foxpodz.de)  <https://github.com/foxpodz/ryuo-iv-screen>
"""
video_matrix.py — find out which video encodes actually play, properly.

The earlier manual probe kept coming back "nothing happened", and the likely
reason is that a config push on its own does not hold. `--config-only` reverts
the screen after about ten seconds, which is roughly how long it takes to look
up, so a clip that works and a clip that doesn't look identical.

This keeps the session alive. For each file it pushes the config, then pumps
telemetry for --hold seconds so the screen stays on that clip while you watch,
then asks.

    # 1. encode a matrix (needs ffmpeg)
    python tests/video_matrix.py --encode source.mp4

    # 2. push them
    adb push out/*.mp4 /sdcard/pcMedia/
    adb shell ls -l /sdcard/pcMedia/          # confirm they landed

    # 3. run the matrix
    python tests/video_matrix.py

    # or test one file you already have
    python tests/video_matrix.py --files myclip.mp4 --hold 15

ALWAYS includes RYUO_IV_HW_Info_02.mp4 as a control. If ASUS's own preset
doesn't play either, the problem is this tool or the media path, not your
encode -- and that is worth knowing before you re-encode anything a fifth time.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ryuo_proto as proto
from probe import Link, ask                # reuse the transport

# The open question is whether 2240x1080 fails because of frame size or because
# `-level 4.0` was pinned on a frame that exceeds Level 4.0's 8192-macroblock
# limit. These three separate those: one native-res clip with an honest level,
# and a pair straddling 8192 exactly.
#
#   1920x1080 = 8160 MB  (just UNDER 8192)
#   2048x1080 = 8704 MB  (just OVER)
#   2240x1080 = 9520 MB  (the one that failed)
LEVEL_TEST = [
    (1920, 1080, "under8192"),
    (2048, 1080, "over8192"),
    (2240, 1080, "honestlevel"),
]

# RESULT of the above: 1920 and 2048 play, 2240 does not. 2048x1080 is 8704
# macroblocks, over Level 4.0's 8192 limit, so the macroblock-ceiling theory is
# dead -- and the honest-level 2240 clip failed too, so the pinned-level theory
# is dead as well. What is left is WIDTH, somewhere between 2048 and 2240.
#
# 2048 = 2^11, which smells like a max texture / surface dimension rather than
# a codec limit. These bisect the gap; if the cutoff is exactly 2048 that is a
# strong tell.
WIDTH_TEST = [
    (2080, 1080, "w2080"),
    (2112, 1080, "w2112"),
    (2176, 1080, "w2176"),
]

# ANSWERED: 2240x1080 H.265 PLAYS. 2240x1080 H.264 does not.
#
# The Rockchip Codec2 declarations said H.264 decode tops out at 1920x1088 while
# HEVC and VP9 go to 4096x2160, and that predicted the result exactly. Native
# resolution was never out of reach -- it just needed a different codec.
# Encoded separately because they need a different codec and fourcc.
HEVC_TEST = [(2240, 1080), (1920, 1080)]

# OPEN: VP9 is declared to the same 4096x2160 as HEVC and has never been sent.
# It has to be VP9-in-MP4 (sample entry vp09): the launcher dispatches on the
# file extension BEFORE anything looks at the codec, and anything that isn't
# .mp4/.gif goes to the still-image loader, so a .webm never reaches a decoder.
# The container is therefore not the question. The question is whether rockit's
# verifyCodecTag accepts vp09 the way it accepts avc1 and hvc1 -- if not, the
# clip falls through to RTConfigMeta and black-screens like oversized H.264.
VP9_TEST = [(2240, 1080), (1920, 1080)]

# codec key -> (filename suffix, ffmpeg args after the input/filter)
ALT_CODECS = {
    # -tag:v hvc1 matters: verifyCodecTag checks the fourcc, and hvc1 is the
    # one Android and rockit expect. hev1 may not be recognised.
    "hevc": ("hevc", ["-c:v", "libx265", "-pix_fmt", "yuv420p", "-crf", "24",
                      "-tag:v", "hvc1"]),
    # vp09 is what ffmpeg's mov muxer writes for VP9 anyway; it is spelled out
    # so the file is unambiguous about what it is testing.
    "vp9":  ("vp9",  ["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", "-crf", "30",
                      "-b:v", "0", "-tag:v", "vp09"]),
}


def encode_alt(src: str, outdir: str, codec: str) -> list[str]:
    """Encode the native-resolution clips for a non-H.264 codec (see ALT_CODECS)."""
    suffix, codec_args = ALT_CODECS[codec]
    sizes = HEVC_TEST if codec == "hevc" else VP9_TEST
    os.makedirs(outdir, exist_ok=True)
    names = []
    for w, h in sizes:
        name = f"t_{w}x{h}_{suffix}.mp4"
        out = os.path.join(outdir, name)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase"
              f":flags=lanczos,setsar=1,crop={w}:{h}")
        cmd = (["ffmpeg", "-y", "-i", src, "-t", "20", "-vf", vf]
               + codec_args
               + ["-maxrate", "8M", "-bufsize", "16M",
                  "-movflags", "+faststart", "-an", out])
        print(f"  encoding {name} ...")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  !! ffmpeg failed for {name}:\n{r.stderr[-600:]}")
            continue
        names.append(name)
    print(f"\n{len(names)} files in {outdir}/")
    print(f"next:  adb push {outdir}/*{suffix}.mp4 /sdcard/pcMedia/")
    print(f"then:  python tests/video_matrix.py --{codec}-test")
    return names

# (width, height, profile) -- the sizes that matter and both profiles
# NOTE: this ladder was how the H.264 width limit was found. The practical
# answer is now simpler -- encode HEVC at 2240x1080 and it just works. Kept
# because it is the evidence for where H.264 stops, and useful on other
# firmware or other Ryuo models.
MATRIX = [
    (1280, 720, "baseline"),      # inside the declared software-codec cap
    (1280, 720, "high"),
    (1920, 926, "baseline"),      # ASUS's own clip geometry
    (1920, 926, "high"),
    (1606, 1080, "baseline"),     # split zone 1 (unusual width by design)
    (2240, 1080, "baseline"),     # panel native -- the one that black-screened
    (2240, 1080, "high"),
]

CONTROL = "RYUO_IV_HW_Info_02.mp4"   # ASUS preset, ships on every unit


def encode(src: str, outdir: str, no_level: bool = False,
           matrix=None) -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    names = []
    for w, h, prof in (matrix if no_level else MATRIX):
        name = f"t_{w}x{h}_{prof}.mp4"
        out = os.path.join(outdir, name)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase"
              f":flags=lanczos,setsar=1,crop={w}:{h}")
        cmd = ["ffmpeg", "-y", "-i", src, "-t", "20", "-vf", vf,
               "-c:v", "libx264",
               # NO -level here: pinning 4.0 on a frame bigger than 8192
               # macroblocks writes an SPS the stream violates.
               "-pix_fmt", "yuv420p", "-crf", "20",
               "-maxrate", "8M", "-bufsize", "16M",
               "-preset", "medium", "-movflags", "+faststart", "-an", out]
        if not no_level:
            cmd[cmd.index("libx264") + 1:cmd.index("libx264") + 1] = [
                "-profile:v", prof]
        print(f"  encoding {name} ...")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  !! ffmpeg failed for {name}:\n{r.stderr[-600:]}")
            continue
        names.append(name)
    print(f"\n{len(names)} files in {outdir}/")
    print(f"next:  adb push {outdir}/*.mp4 /sdcard/pcMedia/")
    return names


def play(link: Link, filename: str, hold: float, play_mode: str) -> None:
    """Push a config for this clip. The Link keepalive holds the session.

    Without a continuous POST all the screen reverts to stock after a few
    seconds -- including while you are looking at it deciding whether the clip
    played. Link.start_keepalive() runs that loop on a background thread, so
    this only has to push the config and wait.
    """
    link.send(proto.POST, proto.RES_CONFIG, proto.config_payload(
        brightness=85,
        config=proto.screen_config(
            media=[filename],
            play_mode=play_mode,
            sysinfo=proto.sysinfo_slots("CPU Temperature", "GPU Temperature",
                                        "Date&Time"))))
    time.sleep(1.6 + hold)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--encode", metavar="SOURCE",
                    help="encode the test matrix from this file and exit")
    ap.add_argument("--level-test", action="store_true",
                    help="encode the three clips that separate 'frame too big' "
                         "from 'we pinned a level the stream violates': "
                         "1920x1080 (8160 MB, under the L4.0 limit), "
                         "2048x1080 (8704, over) and 2240x1080 with no -level")
    ap.add_argument("--width-test", action="store_true",
                    help="bisect the width gap between 2048 (plays) and 2240 "
                         "(fails): 2080, 2112, 2176 at 1080")
    ap.add_argument("--hevc-test", action="store_true",
                    help="H.265 at native 2240x1080. The Rockchip HEVC decoder "
                         "is declared to 4096x2160 while AVC stops at "
                         "1920x1088, so this should play where H.264 doesn't")
    ap.add_argument("--vp9-test", action="store_true",
                    help="VP9-in-MP4 (vp09) at native 2240x1080. Declared to "
                         "4096x2160 like HEVC; untested. The question is "
                         "whether rockit's verifyCodecTag accepts vp09")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--files", nargs="*",
                    help="filenames already in /sdcard/pcMedia/ to test")
    ap.add_argument("--hold", type=float, default=10.0,
                    help="seconds to keep each clip on screen (default 10)")
    ap.add_argument("--play-mode", default=proto.PLAY_SINGLE,
                    choices=proto.PLAY_MODES,
                    help="Single repeats media[0], so it loops one clip")
    ap.add_argument("--no-control", action="store_true",
                    help="skip the ASUS preset sanity check")
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=proto.PID)
    ap.add_argument("--index", type=int, default=None)
    args = ap.parse_args()

    if args.encode:
        if args.hevc_test or args.vp9_test:
            encode_alt(args.encode, args.outdir,
                       "hevc" if args.hevc_test else "vp9")
        else:
            encode(args.encode, args.outdir,
                   args.level_test or args.width_test,
                   WIDTH_TEST if args.width_test else LEVEL_TEST)
        return

    if args.hevc_test:
        files = args.files or [f"t_{w}x{h}_hevc.mp4" for w, h in HEVC_TEST]
    elif args.vp9_test:
        files = args.files or [f"t_{w}x{h}_vp9.mp4" for w, h in VP9_TEST]
    else:
        which = (WIDTH_TEST if args.width_test else
                 LEVEL_TEST if args.level_test else MATRIX)
        files = args.files or [f"t_{w}x{h}_{p}.mp4" for w, h, p in which]
    if not args.no_control:
        files = [CONTROL] + files

    print("=" * 74)
    print("  video matrix — each clip is HELD on screen with a live telemetry")
    print(f"  loop for {args.hold:.0f}s, so nothing reverts under you.")
    print("  Push the files first:  adb push out/*.mp4 /sdcard/pcMedia/")
    print("=" * 74)

    link = Link(args.vid, args.pid, args.index)
    link.start_keepalive()
    results = {}
    try:
        for name in files:
            tag = " (ASUS preset — CONTROL)" if name == CONTROL else ""
            print(f"\n-- {name}{tag}")
            play(link, name, args.hold, args.play_mode)
            a = ask("did it play?", ("y", "n", "static", "skip"))
            results[name] = a
            if name == CONTROL and a == "n":
                print("\n  !! The ASUS preset didn't play either.")
                print("  !! That means the problem is NOT your encode. Check:")
                print("  !!   adb shell ls -l /sdcard/pcMediaPreset/")
                print("  !!   - is the screen even taking config right now?")
                print("  !!   - is Info Hub running and holding the HID handle?")
                if ask("keep going anyway?", ("y", "n")) == "n":
                    break
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        link.known_good()
        link.close()

    print("\n" + "=" * 74)
    for k, v in results.items():
        print(f"  {v:<7} {k}")
    ctrl = results.get(CONTROL)
    plays = [k for k, v in results.items() if v == "y" and k != CONTROL]
    print("=" * 74)
    if ctrl == "n":
        print("  Control failed — treat every other row as meaningless.")
    elif plays:
        print(f"  Playing: {', '.join(plays)}")
        print("  Compare profiles at the same size to see if Baseline is the")
        print("  deciding factor, and sizes at the same profile for a ceiling.")
    else:
        print("  Control played but none of the test encodes did.")
        print("  So it's the encode, not the transport. Next suspect is the")
        print("  container or pixel format rather than size — try remuxing an")
        print("  ASUS preset's exact parameters:")
        print("    adb pull /sdcard/pcMediaPreset/RYUO_IV_HW_Info_02.mp4")
        print("    ffprobe -v error -show_streams RYUO_IV_HW_Info_02.mp4")


if __name__ == "__main__":
    main()
