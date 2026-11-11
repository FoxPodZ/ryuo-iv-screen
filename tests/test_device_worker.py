# SPDX-License-Identifier: GPL-3.0-or-later
import json
import threading
import time
from dataclasses import replace

import pytest
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
        def sample(self):
            return snapshot

        def catalog(self):
            return (SensorDescriptor(ref, "fan.aio.rpm", "AIO Pump", "RPM"),)

        def to_pc_info(self, value, *, extra_readouts=None, fan_aliases=None):
            assert value is snapshot
            assert extra_readouts is None
            return proto.pc_info(fans=[{
                "onBoard": True,
                "name": (fan_aliases or {}).get(
                    ("fan.aio.rpm", ref), "AIO Pump"
                ),
                "value": 1830,
            }])

    telemetry = StructuredTelemetry()
    slots = (
        SlotAssignment(True, "fan.aio.rpm", "Fan Speed Coolant", "Coolant"),
    ) + tuple(SlotAssignment() for _ in range(5))
    worker = DeviceWorker(FakeTransport(), telemetry, state=ScreenState(slots=slots))

    payload = worker._collect_telemetry()

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


def test_six_long_fan_aliases_replace_originals_and_keep_all_frame_bounded():
    measurements = {}
    descriptors = []
    slots = []
    for index in range(6):
        measurement_id = "fan.case{}.rpm".format(index)
        ref = SensorRef("hwmon", "nct6799", "fan{}_input".format(index + 1))
        measurements[measurement_id] = Measurement(
            ref, measurement_id, 1000 + index, "RPM", 1.0, available=True
        )
        descriptors.append(SensorDescriptor(
            ref, measurement_id, "Fan {}".format(index + 1), "RPM"
        ))
        label = "L{}".format(index) + "x" * 30
        slots.append(SlotAssignment(
            True, measurement_id, "Fan Speed " + label, label
        ))
    snapshot = TelemetrySnapshot(measurements, 1.0)

    class StructuredTelemetry:
        def sample(self):
            return snapshot

        def catalog(self):
            return tuple(descriptors)

        def to_pc_info(self, value, *, extra_readouts=None, fan_aliases=None):
            fans = [
                {"onBoard": True,
                 "name": (fan_aliases or {}).get(
                     (descriptor.measurement_id,
                      value.measurements[descriptor.measurement_id].ref),
                     descriptor.label,
                 ),
                 "value": int(value.measurements[descriptor.measurement_id].value)}
                for descriptor in descriptors
            ]
            fans.extend(
                {"onBoard": True, "name": name, "value": int(reading)}
                for name, reading in (extra_readouts or {}).items()
            )
            return proto.pc_info(fans=fans, timestamp_ms=1)

    worker = DeviceWorker(
        FakeTransport(), StructuredTelemetry(),
        state=ScreenState(slots=tuple(slots)),
    )
    payload = worker._collect_telemetry()

    assert len(payload["fans"]) == 6
    assert [fan["name"] for fan in payload["fans"]] == [slot.label for slot in slots]
    DeviceCommand.for_state(ScreenState(slots=tuple(slots))).validated(
        seq=2_147_483_647
    )
    proto.request(proto.POST, proto.RES_ALL, payload, seq=2_147_483_647)


def test_fan_alias_longer_than_safe_protocol_bound_is_rejected():
    with pytest.raises(ValueError, match="slot label must be at most 32"):
        SlotAssignment(
            True, "fan.case.rpm", "Fan Speed " + "x" * 33, "x" * 33
        )


def test_duplicate_fan_display_labels_are_aliased_by_stable_ref():
    first_ref = SensorRef("hwmon", "board-a", "fan1_input")
    second_ref = SensorRef("hwmon", "board-b", "fan1_input")
    snapshot = TelemetrySnapshot({
        "fan.intake.rpm": Measurement(
            first_ref, "fan.intake.rpm", 1100, "RPM", 1.0, available=True
        ),
        "fan.exhaust.rpm": Measurement(
            second_ref, "fan.exhaust.rpm", 900, "RPM", 1.0, available=True
        ),
    }, 1.0)
    descriptors = (
        SensorDescriptor(first_ref, "fan.intake.rpm", "Fan 1", "RPM"),
        SensorDescriptor(second_ref, "fan.exhaust.rpm", "Fan 1", "RPM"),
    )

    class StructuredTelemetry:
        def sample(self):
            return snapshot

        def catalog(self):
            return descriptors

        def to_pc_info(self, value, *, fan_aliases=None):
            aliases = fan_aliases or {}
            return proto.pc_info(fans=[
                {
                    "onBoard": True,
                    "name": aliases.get((key, reading.ref), "Fan 1"),
                    "value": int(reading.value),
                }
                for key, reading in value.measurements.items()
            ], timestamp_ms=1)

    slots = (
        SlotAssignment(True, "fan.intake.rpm", "Fan Speed Intake", "Intake"),
        SlotAssignment(True, "fan.exhaust.rpm", "Fan Speed Exhaust", "Exhaust"),
    ) + tuple(SlotAssignment() for _ in range(4))
    worker = DeviceWorker(
        FakeTransport(), StructuredTelemetry(), state=ScreenState(slots=slots)
    )

    payload = worker._collect_telemetry()

    assert [(fan["name"], fan["value"]) for fan in payload["fans"]] == [
        ("Intake", 1100), ("Exhaust", 900)
    ]


def test_alias_growth_falls_back_to_bounded_original_keepalive_names():
    measurements = {}
    descriptors = []
    slots = []
    for index in range(6):
        key = "fan.case{}.rpm".format(index)
        ref = SensorRef("hwmon", "nct6799", "fan{}_input".format(index + 1))
        measurements[key] = Measurement(ref, key, 1, "RPM", 1.0, available=True)
        descriptors.append(SensorDescriptor(ref, key, "F{}".format(index), "RPM"))
        label = "A{}".format(index) + "x" * 30
        slots.append(SlotAssignment(True, key, "Fan Speed " + label, label))
    snapshot = TelemetrySnapshot(measurements, 1.0)

    class StructuredTelemetry:
        def sample(self):
            return snapshot

        def catalog(self):
            return tuple(descriptors)

        def to_pc_info(self, value, *, fan_aliases=None):
            aliases = fan_aliases or {}
            return proto.pc_info(fans=[
                {
                    "onBoard": True,
                    "name": aliases.get((key, reading.ref), "F{}".format(index)),
                    "value": int(reading.value),
                }
                for index, (key, reading) in enumerate(value.measurements.items())
            ], timestamp_ms=1)

    # Find a runtime magnitude where original names still fit but aliases do
    # not. This avoids coupling the regression to JSON encoder byte counts.
    telemetry = StructuredTelemetry()
    aliases = {
        (slot.measurement_id, snapshot.measurements[slot.measurement_id].ref): slot.label
        for slot in slots
    }
    for digits in range(1, 200):
        huge = 10 ** digits
        for reading in snapshot.measurements.values():
            object.__setattr__(reading, "value", huge)
        original = telemetry.to_pc_info(snapshot)
        aliased = telemetry.to_pc_info(snapshot, fan_aliases=aliases)
        try:
            proto.request(proto.POST, proto.RES_ALL, original, seq=2_147_483_647)
        except ValueError as exc:  # pragma: no cover - aliases must cross first
            raise AssertionError("base telemetry crossed the limit before aliases") from exc
        try:
            proto.request(proto.POST, proto.RES_ALL, aliased, seq=2_147_483_647)
        except ValueError:
            break
    else:  # pragma: no cover - protocol constants would have changed
        raise AssertionError("test could not find the alias-only frame boundary")

    worker = DeviceWorker(
        FakeTransport(), telemetry, state=ScreenState(slots=tuple(slots))
    )
    payload = worker._collect_telemetry()

    assert [fan["name"] for fan in payload["fans"]] == [
        "F{}".format(index) for index in range(6)
    ]
    proto.request(proto.POST, proto.RES_ALL, payload, seq=2_147_483_647)


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

        def to_pc_info(self, snapshot, *, fan_aliases=None):
            assert not fan_aliases
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
