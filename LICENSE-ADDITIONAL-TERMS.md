# Additional terms

Everything in this repository — the source code, `README.md`, `PROTOCOL.md`, the
udev rule and the captures under `captures/` — is licensed under the **GNU
General Public License, version 3, or (at your option) any later version**
(`GPL-3.0-or-later`). The full text is in [LICENSE](LICENSE).

In accordance with **section 7(b)** of the GPL v3, the following additional term
applies:

> You must preserve the author attribution — "FoxPodZ (foxpodz.de)" and a link
> to <https://github.com/foxpodz/ryuo-iv-screen> — in every file from this
> repository that carries it, source code and documentation alike, and in the
> Appropriate Legal Notices (an "About", "Credits" or equivalent screen) of any
> work that displays them.

That is the two places section 7(b) names — "that material" and the
"Appropriate Legal Notices" — and nothing beyond them. It is a permitted
additional term, not a modification of the GPL and not a further restriction. It does not restrict any freedom the GPL
grants you: you may still use, study, modify, redistribute and sell this
software and these documents, including as part of a larger work, so long as
that work is also released under the GPL and this attribution survives.

Credit is the only thing being asked for here.

## What is *not* covered by any of this

The protocol itself. Frame layouts, checksum algorithms, field names and JSON
schemas are facts about a device ASUS and Baiyi built, not creative expression
of mine. Anyone is free to read `PROTOCOL.md` and write a clean-room
implementation in any language under any licence they like — and honestly,
please do. The licence above covers my particular *wording* and my particular
*code*, nothing more.

No ASUS or Baiyi firmware, APKs or decompiled source files are redistributed
here. Short identifiers quoted from their software — field names, string
constants, message numbers — are named for accuracy, not copied for reuse, and
code-like illustrations of control flow are paraphrases. The captures in
`captures/` are my own logs of my own device, with the host's hardware
identifiers replaced by placeholders.
