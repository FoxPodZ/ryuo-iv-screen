#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 FoxPodZ (foxpodz.de)
"""
Tests for the shared read/write loop in ryuo_hid. No hardware needed: the
device handle is a fake that hands back whatever reports it was loaded with.

    pytest tests/ -v

These pin the two things the old copy-pasted loops got wrong: taking the
first reply that decoded, whoever it belonged to, and giving up on a reply
that arrived behind a fragment that didn't decode.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ryuo_hid
import ryuo_proto as proto


class FakeHandle:
    """hidapi-shaped: write() returns the byte count, read() is non-blocking
    and returns one report per call, or [] when nothing is waiting."""

    def __init__(self, *reports):
        self.inbox = list(reports)
        self.written = []

    def write(self, data):
        self.written.append(bytes(data))
        return len(data)

    def read(self, n):
        return list(self.inbox.pop(0)) if self.inbox else []


def report(ack, content=""):
    body = proto.build_body("1 200", content, ack=ack)
    return proto.pad_for_hid(proto.encode(body))


def test_write_frame_is_one_report_with_report_id():
    h = FakeHandle()
    ryuo_hid.write_frame(h, proto.request(proto.GET, proto.RES_SPEC, seq=1))
    assert len(h.written) == 1
    assert h.written[0][0] == 0 and len(h.written[0]) == proto.REPORT_SIZE + 1


def test_write_frame_refuses_anything_but_one_report():
    with pytest.raises(ValueError):
        ryuo_hid.write_frame(FakeHandle(), b"\x5a\x5a")


def test_skips_replies_to_other_requests():
    """A backlog from earlier requests, then ours. Must return ours."""
    h = FakeHandle(report(4), report(5), report(50001), report(8))
    log = []
    body = ryuo_hid.read_reply(h, seq=7, timeout=0.5, log=log.append)
    assert proto.reply_ack(body) == 8
    assert len(log) == 3
    assert all(m.startswith(ryuo_hid.SKIP_FOREIGN) for m in log)


def test_reply_that_never_comes_is_none_not_someone_elses():
    """`transported` never replies. The old loop would have reported the next
    stray reply as its answer; this must time out instead."""
    h = FakeHandle(report(3), report(4))
    assert ryuo_hid.read_reply(h, seq=9, timeout=0.1) is None


def test_reply_without_ack_is_skipped():
    body = proto.build_body("1 200", "")
    h = FakeHandle(proto.pad_for_hid(proto.encode(body)), report(2))
    assert proto.reply_ack(ryuo_hid.read_reply(h, seq=1, timeout=0.5)) == 2


def test_recovers_after_a_stray_tail_report():
    long = proto.pad_for_hid(proto.encode(
        proto.build_body("1 200", "x" * 1500, ack=8)))
    h = FakeHandle(long[proto.REPORT_SIZE:], report(10))
    log = []
    body = ryuo_hid.read_reply(h, seq=9, timeout=0.5, log=log.append)
    assert proto.reply_ack(body) == 10
    assert log and log[0].startswith(ryuo_hid.SKIP_UNDECODABLE)


def test_reassembles_a_reply_spanning_two_reports():
    """The 1227-byte `conn` reply case from PROTOCOL.md §2."""
    long = proto.pad_for_hid(proto.encode(
        proto.build_body("1 200", '{"media":"' + "y" * 1400 + '"}', ack=2)))
    assert len(long) == 2 * proto.REPORT_SIZE
    h = FakeHandle(long[:proto.REPORT_SIZE], long[proto.REPORT_SIZE:])
    body = ryuo_hid.read_reply(h, seq=1, timeout=0.5)
    assert proto.reply_json(body) == {"media": "y" * 1400}


def test_transact_with_zero_timeout_does_not_read():
    h = FakeHandle(report(2))
    assert ryuo_hid.transact(h, proto.POST, proto.RES_PRESET, {}, seq=1,
                             timeout=0) is None
    assert len(h.inbox) == 1, "the reply must be left for a later read"


def test_drain_reads_everything_waiting_without_blocking():
    h = FakeHandle(report(2), report(3), report(4))
    seen = []
    assert ryuo_hid.drain(h, seen.append) == 3
    assert [proto.reply_ack(b) for b in seen] == [2, 3, 4]
    assert ryuo_hid.drain(h) == 0                 # nothing left, returns at once
