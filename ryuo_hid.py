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
ryuo_hid.py — the write/read loop every script here shares.

ryuo_proto.py builds and parses frames and does no I/O. This is the small
part that touches a device handle: write one report, then read until the
reply to *that* request turns up. It used to be copy-pasted into
ryuo_send.py, ryuo_ctl.py and tests/probe.py, and all three copies took the
first frame that decoded as the answer, whoever it belonged to.

`h` is anything with hidapi's device interface: write(bytes) -> int and a
non-blocking read(n) -> list[int] (empty when nothing is waiting). It doesn't
import hid itself, so the tests can hand it a fake.
"""
from __future__ import annotations

import time

import ryuo_proto as proto

# Prefixes of the two kinds of message read_reply() passes to `log`.
SKIP_FOREIGN = "skipped a reply that isn't ours"
SKIP_UNDECODABLE = "skipped a frame that doesn't decode"


def write_frame(h, frame: bytes) -> None:
    """Write one request as one report, with report id 0 in front.

    No loop over reports, on purpose: the device drops a frame that spills
    into a second report (PROTOCOL.md §2), and proto.request() already refuses
    to build one, so a request is always exactly one 1024-byte report.
    """
    if len(frame) != proto.REPORT_SIZE:
        raise ValueError(f"expected one {proto.REPORT_SIZE}-byte report from "
                         f"proto.request(), got {len(frame)} bytes")
    if h.write(b"\x00" + frame) < 0:
        raise OSError("HID write failed")


def read_reply(h, seq: int, timeout: float, log=None) -> str | None:
    """Read until the reply to `seq` arrives; return its body, or None.

    Anything else that arrives first is skipped: replies to earlier requests
    still draining from the device's queue, replies to another program using
    the cooler at the same time (the OS gives each open handle a copy of every
    reply), and fragments that don't decode. `log(msg)`, if given, is called
    once per skipped frame.

    The buffer is local to the call. Every reply the device sends starts on a
    report boundary (it pads each one out to whole reports), so once the
    matching reply is found, what's left is that report's padding.
    """
    buf = bytearray()
    deadline = time.monotonic() + timeout

    def bad(ex, raw):
        if log:
            log(f"{SKIP_UNDECODABLE} ({ex}): "
                f"{raw[:16].hex(' ').upper()}")

    while True:
        while (body := proto.pop_reply(buf, on_error=bad)) is not None:
            if proto.is_reply_to(body, seq):
                return body
            if log:
                ack = proto.reply_ack(body)
                whose = (f"seq {ack - 1}" if ack is not None
                         else "no AckNumber")
                status = body.split("\r\n", 1)[0]
                log(f"{SKIP_FOREIGN} ({whose}, we sent "
                    f"seq {seq}): {status!r}")
        if time.monotonic() >= deadline:
            return None
        data = h.read(proto.REPORT_SIZE)
        if data:
            buf += bytes(data)
        else:
            time.sleep(0.01)


def drain(h, log=None) -> int:
    """Read and decode whatever replies are already waiting, without blocking.

    For a loop that sends on a fixed clock and doesn't need its replies:
    waiting for one would stall the loop for as long as the device's reply
    queue is deep. Returns how many replies were read; `log(body)` is called
    for each. A long reply whose second report hasn't arrived yet is cut in
    half here -- the next drain() or read_reply() resyncs past the tail.
    """
    buf, n = bytearray(), 0
    while True:
        data = h.read(proto.REPORT_SIZE)
        if not data:
            return n
        buf += bytes(data)
        while (body := proto.pop_reply(buf)) is not None:
            n += 1
            if log:
                log(body)


def transact(h, method: str, resource: str, payload=None, *, seq: int,
             timeout: float, log=None) -> str | None:
    """Send one request and return the body of the reply to it, or None.

    timeout=0 sends without reading at all -- the reply is left for a later
    read_reply() to skip past.
    """
    write_frame(h, proto.request(method, resource, payload, seq=seq))
    if timeout <= 0:
        return None
    return read_reply(h, seq, timeout, log)
