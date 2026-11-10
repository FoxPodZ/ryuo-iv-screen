# SPDX-License-Identifier: GPL-3.0-or-later
import json
import threading
import time
from dataclasses import replace

import ryuo_proto as proto
from ryuo_screen.device import DeviceCommand, DeviceWorker
from ryuo_screen.store import ScreenState


def _reply(payload):
    return "1 200\r\n\r\n" + json.dumps(payload)


class MutableClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class RecoveringTransport:
    def __init__(self, open_failures=0):
        self.open_failures = open_failures
        self.opens = 0
        self.calls = []
        self.fail_resource = None
        self.failed = threading.Event()
        self.allow_reopen = threading.Event()
        self.allow_reopen.set()

    def open(self):
        self.opens += 1
        if self.opens > 1:
            self.allow_reopen.wait(2)
        if self.opens <= self.open_failures:
            raise OSError("device missing")

    def close(self):
        pass

    def transact(self, method, resource, payload, *, seq, timeout):
        self.calls.append((seq, resource, payload))
        if resource == self.fail_resource:
            self.fail_resource = None
            self.failed.set()
            raise OSError("USB removed")
        if resource == proto.RES_CONN:
            return _reply({
                "model": "ROG RYUO IV Miku WW",
                "firmware": "1.0.10",
                "sn": "ABC123",
                "serialNumber": "ABC123",
            })
        return None

    def drain(self, limit=32):
        return 0


def _wait(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not reached")


def test_open_backoff_reenumerates_and_configures_in_required_order():
    transport = RecoveringTransport(open_failures=1)
    worker = DeviceWorker(
        transport,
        telemetry=lambda: proto.pc_info(timestamp_ms=1),
        state=ScreenState(),
        keepalive_interval=0.05,
        settle_seconds=0.01,
        reconnect_backoff=(0.01, 0.02),
        max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: worker.status().connected)
        _wait(lambda: any(resource == proto.RES_ALL for _, resource, _ in transport.calls))
        status = worker.status()
    finally:
        worker.stop()
    assert transport.opens >= 2
    assert [resource for _, resource, _ in transport.calls[:3]] == [
        proto.RES_CONN, proto.RES_CONFIG, proto.RES_ALL
    ]
    assert status.descriptor["sn"] == "<redacted>"
    assert status.descriptor["serialNumber"] == "<redacted>"
    assert status.model == "ROG RYUO IV Miku WW"
    assert status.firmware == "1.0.10"


def test_write_failure_recovers_and_applies_latest_saved_state_once():
    transport = RecoveringTransport()
    worker = DeviceWorker(
        transport,
        telemetry=lambda: proto.pc_info(),
        state=ScreenState(),
        keepalive_interval=0.05,
        settle_seconds=0,
        reconnect_backoff=(0.01,),
        max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: worker.status().connected)
        transport.allow_reopen.clear()
        transport.fail_resource = proto.RES_PRESET
        failed = worker.submit(DeviceCommand(proto.POST, proto.RES_PRESET, {"x": 1}))
        assert transport.failed.wait(1)
        pending_state = replace(ScreenState(), brightness=33)
        pending = worker.submit(DeviceCommand.for_state(pending_state))
        transport.allow_reopen.set()
        _wait(lambda: worker.status().connected and worker.status().recovery_count >= 1)
        assert pending.wait(2).applied
        assert failed.wait(2).error
    finally:
        transport.allow_reopen.set()
        worker.stop()
    configs = [payload for _, resource, payload in transport.calls if resource == proto.RES_CONFIG]
    assert [payload["waterBlockScreen"]["brightness"] for payload in configs].count(33) == 1


def test_boottime_gap_forces_reconnect_and_fresh_handshake():
    transport = RecoveringTransport()
    clock = MutableClock()
    worker = DeviceWorker(
        transport,
        telemetry=lambda: proto.pc_info(),
        state=ScreenState(),
        keepalive_interval=0.1,
        settle_seconds=0,
        reconnect_backoff=(0.01,),
        max_rate=1000000000,
        clock=clock,
        resume_gap_seconds=5,
    )
    worker.start()
    try:
        _wait(lambda: worker.status().connected)
        before = transport.opens
        clock.advance(10)
        wake = worker.submit(DeviceCommand(proto.POST, proto.RES_PRESET, {}))
        _wait(lambda: transport.opens > before and worker.status().connected)
        assert wake.wait(2).applied
    finally:
        worker.stop()
    assert len([call for call in transport.calls if call[1] == proto.RES_CONN]) >= 2
