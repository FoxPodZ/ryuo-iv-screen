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


class FakeTransport:
    def __init__(self):
        self.opened = False
        self.calls = []
        self.lock = threading.Lock()
        self.block_resource = None
        self.blocked = threading.Event()
        self.release = threading.Event()

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def transact(self, method, resource, payload, *, seq, timeout):
        with self.lock:
            self.calls.append((threading.get_ident(), seq, method, resource, payload, timeout))
        if resource == self.block_resource:
            self.blocked.set()
            self.release.wait(2)
        if resource == proto.RES_CONN:
            return _reply({"model": "ROG RYUO IV", "firmware": "1.0.10", "sn": "secret"})
        return None

    def drain(self, limit=32):
        return 0


def _wait(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not reached")


def test_all_transport_io_and_sequences_are_owned_by_one_worker_thread():
    transport = FakeTransport()
    worker = DeviceWorker(
        transport,
        telemetry=lambda: proto.pc_info(timestamp_ms=1),
        state=ScreenState(),
        keepalive_interval=0.04,
        settle_seconds=0,
        max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: worker.status().connected)
        tickets = []

        def submit(index):
            tickets.append(worker.submit(DeviceCommand(
                proto.POST, proto.RES_PRESET, {"index": index}, priority=50
            )))

        threads = [threading.Thread(target=submit, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for ticket in tickets:
            assert ticket.wait(2).applied
        _wait(lambda: len([call for call in transport.calls if call[3] == proto.RES_ALL]) >= 2)
    finally:
        worker.stop()

    ids = {call[0] for call in transport.calls}
    sequences = [call[1] for call in transport.calls]
    assert len(ids) == 1
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))


def test_queue_is_bounded_and_equivalent_commands_coalesce():
    transport = FakeTransport()
    transport.block_resource = "block"
    worker = DeviceWorker(
        transport,
        telemetry=lambda: proto.pc_info(),
        state=ScreenState(),
        keepalive_interval=10,
        settle_seconds=0,
        max_rate=200,
        queue_size=2,
    )
    worker.start()
    try:
        _wait(lambda: worker.status().connected)
        first = worker.submit(DeviceCommand(proto.POST, "block", {}, priority=50))
        assert transport.blocked.wait(1)
        old = worker.submit(DeviceCommand(
            proto.POST, proto.RES_PRESET, {"version": 1}, coalesce_key="visual"
        ))
        newest = worker.submit(DeviceCommand(
            proto.POST, proto.RES_PRESET, {"version": 2}, coalesce_key="visual"
        ))
        second = worker.submit(DeviceCommand(proto.POST, "second", {}))
        rejected = worker.submit(DeviceCommand(proto.POST, "overflow", {}))
        rejected_state = worker.submit(DeviceCommand.for_state(
            replace(ScreenState(), brightness=22)
        ))
        assert worker.status().queue_depth == 2
        assert old.wait(1).error == "superseded"
        assert rejected.wait(1).queued is False
        assert rejected_state.wait(1).queued is False
        transport.release.set()
        assert first.wait(2).applied
        assert newest.wait(2).applied
        assert second.wait(2).applied
    finally:
        transport.release.set()
        worker.stop()
    sent = [call for call in transport.calls if call[3] == proto.RES_PRESET]
    assert [call[4] for call in sent] == [{"version": 2}]
    configs = [call[4] for call in transport.calls if call[3] == proto.RES_CONFIG]
    assert all(payload["waterBlockScreen"]["brightness"] != 22 for payload in configs)


def test_keepalive_uses_last_safe_payload_when_collection_fails_and_waiter_is_slow():
    transport = FakeTransport()
    count = {"value": 0}
    safe = proto.pc_info(cpu={"load": 17}, timestamp_ms=123)

    def telemetry():
        count["value"] += 1
        if count["value"] > 1:
            raise RuntimeError("sensor down")
        return safe

    worker = DeviceWorker(
        transport,
        telemetry=telemetry,
        state=ScreenState(),
        keepalive_interval=0.03,
        settle_seconds=0,
        max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: len([call for call in transport.calls if call[3] == proto.RES_ALL]) >= 4)
        # A consumer may keep a ticket without waiting; the worker cadence is independent.
        unused_ticket = worker.submit(DeviceCommand(proto.POST, proto.RES_PRESET, {}))
        _wait(lambda: unused_ticket.done)
    finally:
        worker.stop()
    all_payloads = [call[4] for call in transport.calls if call[3] == proto.RES_ALL]
    assert len(all_payloads) >= 4
    assert all(payload == safe for payload in all_payloads)


def test_sequence_growth_cannot_turn_accepted_command_into_unfinished_ticket():
    transport = FakeTransport()
    worker = DeviceWorker(
        transport,
        telemetry=lambda: proto.pc_info(),
        state=ScreenState(),
        keepalive_interval=10,
        settle_seconds=0,
        max_rate=200,
    )
    payload = None
    for size in range(800, 1000):
        candidate = {"pad": "x" * size}
        try:
            proto.request(proto.POST, "borderline", candidate, seq=1)
        except ValueError:
            continue
        try:
            proto.request(proto.POST, "borderline", candidate, seq=10)
        except ValueError:
            payload = candidate
            break
    assert payload is not None, "test must find the one-digit/two-digit frame boundary"

    worker.start()
    try:
        _wait(lambda: worker.status().connected)
        with worker._condition:
            worker._sequence = 10
        ticket = worker.submit(DeviceCommand(proto.POST, "borderline", payload))
        result = ticket.wait(1)
        assert ticket.done
        assert result.applied is False
        assert result.error and "1024-byte report" in result.error
    finally:
        worker.stop()
    assert not any(call[3] == "borderline" for call in transport.calls)
