<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Split-zone geometry measurement

`adb exec-out screencap -p > split.png` taken during a live split-mode session
on firmware 1.0.10, with a solid red image in zone 1 and a solid green one in
zone 2.

```
image size            2240 x 1080
colour transition     x = 1606   (checked at y = 5, 200, 540, 900, 1075)
zone 1 (main face)    1606 px
zone 2 (side strip)    634 px
```

This confirms the layout resource — `home_layout2` is a hardcoded `634px` and
`home_layout1` is `layout_weight="1.0"`, taking the remaining 1606 — and rules
out the 1600 / 640 split implied by the aspect ratios Info Hub's crop tool
enforces. ASUS's tooling and ASUS's layout disagree by 6 px.

## Reproducing it

```bash
# two solid-colour images, one per zone
adb push red.png green.png /sdcard/pcMedia/
python ryuo_send.py --media red.png --media2 green.png
# in another shell, while it's running:
adb exec-out screencap -p > split.png
```

Then find the column where the two colours meet. The `ryuo_send.py` process has
to stay running: `POST all` is a dead-man's switch and the screen drops to
standby about ten seconds after it stops (PROTOCOL.md §10).

## Incidental findings from the same capture

The widget labels are the shortened `subTitle` forms, not the item strings sent:
`CPU Temperature` and `CPU Voltage` **both** render as `CPU`, distinguishable
only by their units (`32°C` vs `1.089V`), and `Fan Speed Chassis4` renders as
`Chassis4`. See PROTOCOL.md §10.

The capture also re-confirms that voltage units render as `V` — an earlier
source read had suggested they might print a literal `2`, from a decompiler
substituting `ExifInterface.GPS_MEASUREMENT_INTERRUPTED`, whose value is in fact
`"V"`.

The screenshot itself is not committed — it is two solid colours and some
numbers, and the measurements above are the whole content.
