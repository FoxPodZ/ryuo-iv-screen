# SPDX-License-Identifier: GPL-3.0-or-later
import json
import threading
import time
from dataclasses import replace

import ryuo_proto as proto
from ryuo_screen.device import DeviceCommand, DeviceWorker, LatestTelemetry
from ryuo_screen.models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot
from ryuo_screen.store import ScreenState, SlotAssignment


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


def test_custom_fan_slot_label_gets_matching_keepalive_alias():
    ref = SensorRef("hwmon", "nct6799", "fan2_input")
    snapshot = TelemetrySnapshot({
        "fan.aio.rpm": Measurement(
            ref, "fan.aio.rpm", 1830, "RPM", 1.0, available=True
        )
    }, 1.0)

    class StructuredTelemetry:
        extra = None

        def sample(self):
            return snapshot

        def catalog(self):
            return (SensorDescriptor(ref, "fan.aio.rpm", "AIO Pump", "RPM"),)

        def to_pc_info(self, value, *, extra_readouts=None):
            assert value is snapshot
            self.extra = extra_readouts
            return proto.pc_info(fans=[
                {"onBoard": True, "name": name, "value": int(reading)}
                for name, reading in (extra_readouts or {}).items()
            ])

    telemetry = StructuredTelemetry()
    slots = (
        SlotAssignment(True, "fan.aio.rpm", "Fan Speed Coolant", "Coolant"),
    ) + tuple(SlotAssignment() for _ in range(5))
    worker = DeviceWorker(FakeTransport(), telemetry, state=ScreenState(slots=slots))

    payload = worker._collect_telemetry()

    assert telemetry.extra == {"Coolant": 1830}
    assert payload["fans"] == [
        {"onBoard": True, "name": "Coolant", "value": 1830}
    ]


def test_thermal_rgb_builds_incremental_preset_from_owner_snapshot():
    ref = SensorRef("amd", "0000:03:00.0", "temp1_input")
    snapshot = TelemetrySnapshot({
        "gpu.temperature": Measurement(
            ref, "gpu.temperature", 70, "C", 1.0, available=True
        )
    }, 1.0)
    state = ScreenState(
        rgb_mode="thermal", rgb_target="both", thermal_source="gpu.temperature"
    )
    worker = DeviceWorker(FakeTransport(), lambda: proto.pc_info(), state=state)
    worker._latest_telemetry = LatestTelemetry(snapshot)

    payload = worker._dynamic_preset_payload(2.0)

    assert payload["settings"]["titleColor"] == proto.thermal_hex(70)
    assert payload["settings"]["contentColor"] == proto.thermal_hex(70)


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


def test_latest_telemetry_cache_is_populated_only_by_owner_thread_and_is_defensive():
    class RecordingTelemetry:
        def __init__(self):
            self.sample_threads = []
            self.catalog_threads = []
            self.ref = SensorRef("test", "device", "temp1")

        def sample(self):
            self.sample_threads.append(threading.get_ident())
            return TelemetrySnapshot(
                {
                    "cpu.temperature": Measurement(
                        self.ref, "cpu.temperature", 41.0, "C", time.time()
                    )
                },
                time.time(),
            )

        def catalog(self):
            self.catalog_threads.append(threading.get_ident())
            return (
                SensorDescriptor(
                    self.ref, "cpu.temperature", "CPU", "C", source="/sys/test/temp1"
                ),
            )

        def to_pc_info(self, snapshot):
            return proto.pc_info(cpu={"temperature": 41}, timestamp_ms=1)

    transport = FakeTransport()
    telemetry = RecordingTelemetry()
    worker = DeviceWorker(
        transport,
        telemetry,
        state=ScreenState(),
        keepalive_interval=0.02,
        settle_seconds=0,
        max_rate=200,
    )
    initial = worker.latest_telemetry()
    assert isinstance(initial, LatestTelemetry)
    assert initial.snapshot is None
    assert initial.error == "telemetry has not been sampled"

    worker.start()
    try:
        _wait(lambda: len(telemetry.sample_threads) >= 2)
        owner_ids = {call[0] for call in transport.calls}
        assert set(telemetry.sample_threads + telemetry.catalog_threads) == owner_ids
        cached = worker.latest_telemetry()
        assert cached.error is None
        assert cached.snapshot.measurements["cpu.temperature"].value == 41.0
        assert cached.catalog[0].source == "/sys/test/temp1"
        cached.snapshot.measurements.clear()
        assert "cpu.temperature" in worker.latest_telemetry().snapshot.measurements
        # Reading from this test thread never calls the provider.
        before = (len(telemetry.sample_threads), len(telemetry.catalog_threads))
        worker.latest_telemetry()
        assert (len(telemetry.sample_threads), len(telemetry.catalog_threads)) == before
    finally:
        worker.stop()


def test_latest_telemetry_cache_reports_error_when_first_collection_fails():
    class BrokenTelemetry:
        def sample(self):
            raise RuntimeError("collector unavailable")

    worker = DeviceWorker(
        FakeTransport(),
        BrokenTelemetry(),
        state=ScreenState(),
        keepalive_interval=0.02,
        settle_seconds=0,
        max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: worker.latest_telemetry().error == "collector unavailable")
        assert worker.latest_telemetry().snapshot is None
        assert worker.latest_telemetry().catalog == ()
    finally:
        worker.stop()
