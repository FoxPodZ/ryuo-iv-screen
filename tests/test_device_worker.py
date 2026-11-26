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
            return _reply({"model": "ROG RYUO IV", "firmware": "1.0.10", "sn": "secret", "media": {"preset": [], "custom": []}})
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

    payload, _ = worker._collect_telemetry()

    assert payload["fans"] == [
        {"onBoard": True, "name": "Coolant", "value": 1830}
    ]


def test_thermal_rgb_builds_incremental_preset_from_owner_snapshot():
    ref = SensorRef("amd", "0000:03:00.0", "temp1_input")
    snapshot = TelemetrySnapshot({
        "gpu.temperature": Measurement(
            ref, "gpu.temperature", 70, "C", time.time(), available=True
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
    payload, _ = worker._collect_telemetry()

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

    payload, _ = worker._collect_telemetry()

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

    transport = FakeTransport()
    worker = DeviceWorker(
        transport, telemetry, state=ScreenState(slots=tuple(slots)),
        keepalive_interval=0.02, settle_seconds=0, max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: len([
            call for call in transport.calls if call[3] == proto.RES_ALL
        ]) >= 3)
        status = worker.status()
        assert status.phase == "degraded"
        assert status.last_error == "fan alias frame overflow"
        base_payloads = [
            call[4] for call in transport.calls if call[3] == proto.RES_ALL
        ]
        base_names = ["F{}".format(index) for index in range(6)]
        assert all(
            [fan["name"] for fan in payload["fans"]] == base_names
            for payload in base_payloads
        )
        assert len([call for call in transport.calls if call[3] == proto.RES_CONN]) == 1

        snapshot = TelemetrySnapshot({
            key: replace(reading, value=1000)
            for key, reading in snapshot.measurements.items()
        }, 1.0)
        alias_names = [slot.label for slot in slots]
        _wait(lambda: (
            worker.status().phase == "healthy"
            and worker.status().last_error is None
            and any(
                call[3] == proto.RES_ALL
                and [fan["name"] for fan in call[4]["fans"]] == alias_names
                for call in transport.calls
            )
        ))
        assert len([call for call in transport.calls if call[3] == proto.RES_CONN]) == 1
    finally:
        worker.stop()


def test_oversized_base_telemetry_keeps_last_safe_payload_without_reconnect():
    transport = FakeTransport()
    calls = {"count": 0}
    safe = proto.pc_info(cpu={"load": 23}, timestamp_ms=1)
    oversized = proto.pc_info(
        fans=[{"onBoard": True, "name": "Fan", "value": 10 ** 2000}],
        timestamp_ms=2,
    )

    def telemetry():
        calls["count"] += 1
        return safe if calls["count"] == 1 else oversized

    worker = DeviceWorker(
        transport, telemetry, state=ScreenState(),
        keepalive_interval=0.02, settle_seconds=0, max_rate=200,
    )
    worker.start()
    try:
        _wait(lambda: len([
            call for call in transport.calls if call[3] == proto.RES_ALL
        ]) >= 3)
        _wait(lambda: worker.status().phase == "degraded")
        assert worker.status().last_error
        assert "1024-byte report" in worker.status().last_error
    finally:
        worker.stop()

    payloads = [call[4] for call in transport.calls if call[3] == proto.RES_ALL]
    assert payloads and all(payload == safe for payload in payloads)
    assert len([call for call in transport.calls if call[3] == proto.RES_CONN]) == 1


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


def test_runtime_selectors_are_applied_by_owner_before_sampling():
    from ryuo_screen.models import SensorRef, TelemetrySnapshot

    observed = []
    ref = SensorRef("amd", "0000:08:00.0", "gpu.load")

    class Collector:
        def set_selectors(self, selectors):
            observed.append(("select", threading.get_ident(), dict(selectors)))

        def sample(self):
            observed.append(("sample", threading.get_ident(), None))
            return TelemetrySnapshot({}, 1)

        def catalog(self):
            return ()

        def to_pc_info(self, snapshot):
            return proto.pc_info(timestamp_ms=1000)

    transport = FakeTransport()
    worker = DeviceWorker(transport, Collector(), state=ScreenState(sensor_selectors={"gpu": ref}))
    worker.start()
    try:
        _wait(lambda: any(entry[0] == "sample" for entry in observed))
        assert observed[0] == ("select", transport.calls[0][0], {"gpu": ref})
        assert observed[1] == ("sample", transport.calls[0][0], None)
    finally:
        worker.stop()


@pytest.mark.parametrize("vid,pid,interface", [(0xffff, proto.PID, 0), (proto.VID, 0xffff, 0), (proto.VID, proto.PID, 1)])
def test_auto_open_requires_complete_screen_identity(vid, pid, interface):
    from ryuo_screen.device import HidTransport

    class Hid:
        def enumerate(self, *args):
            return [dict(path=b"stub", vendor_id=vid, product_id=pid, interface_number=interface)]

        def device(self):
            pytest.fail("unmatched HID opened")

    with pytest.raises(OSError):
        HidTransport(Hid()).open()


class CatalogTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        self.reply = _reply({"version": {"firmware": "V1.0.10"}, "media": {"preset": [], "custom": ["mine.png"]}})

    def transact(self, method, resource, payload, **args):
        super().transact(method, resource, payload, **args)
        if resource == proto.RES_CONN:
            return self.reply
        if resource == proto.RES_MEDIA_DELETE:
            return _reply({})


@pytest.mark.parametrize("body", [None, _reply({}), _reply({"media": {"preset": []}})])
def test_handshake_requires_complete_catalog(body):
    t = CatalogTransport()
    t.reply = body
    w = DeviceWorker(t, lambda: proto.pc_info(), settle_seconds=0)
    with pytest.raises(OSError):
        w._connect()
    assert not w.status().connected
    assert not any(call[3] == proto.RES_CONFIG for call in t.calls)


def test_capture_firmware_and_clear_catalog_on_disconnect():
    t = CatalogTransport()
    w = DeviceWorker(t, lambda: proto.pc_info(), settle_seconds=0, max_rate=1000)
    w._connect()
    assert w.status().firmware == "V1.0.10"
    w._mark_disconnected(OSError("lost"))
    assert w.status().descriptor == {}


def test_reconnect_revalidates_pending_profile_before_writing_config():
    t = CatalogTransport()
    s = ScreenState(active_profile="pending", media=(("missing.mp4",),))
    w = DeviceWorker(t, lambda: proto.pc_info(), state=s, settle_seconds=0, max_rate=1000)
    w._connect()
    assert not any(call[3] == proto.RES_CONFIG for call in t.calls)
    assert w.status().connected and "missing.mp4" in w.status().last_error


@pytest.mark.parametrize("change", ["reconnect", "expiry", "invalid_refresh", "valid_refresh"])
def test_delete_bound_to_admitted_catalog_and_deadline(change):
    t = CatalogTransport()
    t.block_resource = "barrier"
    w = DeviceWorker(t, lambda: proto.pc_info(), settle_seconds=0, max_rate=1000)
    w.start()
    try:
        _wait(lambda: w.status().connected)
        w.submit(DeviceCommand(proto.POST, "barrier"))
        assert t.blocked.wait(1)
        generation = w.status().catalog_generation
        deadline = time.monotonic() + (-1 if change == "expiry" else 2)
        delete = w.submit(DeviceCommand(proto.POST, proto.RES_MEDIA_DELETE,
            {"include": ["mine.png"]}, expect_reply=True, catalog_generation=generation, deadline=deadline))
        if change == "reconnect":
            w.notify_resume()
        elif change == "invalid_refresh":
            t.reply = None
        elif change == "valid_refresh":
            t.reply = _reply({"media": {"preset": [], "custom": []}})
        t.release.set()
        result = delete.wait(2)
        assert result.applied == (change == "valid_refresh")
        assert bool([c for c in t.calls if c[3] == proto.RES_MEDIA_DELETE]) == (change.endswith("refresh"))
        if change == "valid_refresh":
            assert w.status().descriptor["media"]["custom"] == []
    finally:
        t.release.set()
        w.stop()


def test_sampling_interval_changes_without_changing_wire_heartbeat():
    samples = []
    def sample():
        samples.append(time.monotonic())
        return proto.pc_info()
    transport = FakeTransport()
    worker = DeviceWorker(transport, sample, state=ScreenState(refresh_interval=20),
                          keepalive_interval=.025, settle_seconds=0, max_rate=1000)
    worker.start()
    try:
        _wait(lambda: len([c for c in transport.calls if c[3] == proto.RES_ALL]) >= 4)
        assert len(samples) == 1
        worker.submit(DeviceCommand.for_state(ScreenState(refresh_interval=.1)))
        _wait(lambda: len(samples) >= 3)
        worker.submit(DeviceCommand.for_state(ScreenState(refresh_interval=30)))
        count = len(samples)
        heartbeats = len(transport.calls)
        _wait(lambda: len(transport.calls) >= heartbeats + 4)
        assert len(samples) == count
    finally:
        worker.stop()


@pytest.mark.parametrize("failure", ["%", "RPM", "W", "stale", "missing", "collection error"])
def test_loss_of_fresh_celsius_restores_static_preset_once(failure):
    state = ScreenState(rgb_mode="thermal")
    ref = SensorRef("cpu", "cpu", "temperature")
    reading = Measurement(ref, state.thermal_source, 70, "°C", time.time())
    frames = [TelemetrySnapshot({state.thermal_source: reading}, time.time())]
    class Collector:
        def sample(self):
            if not frames:
                raise RuntimeError("sensor read failed")
            return frames[-1]
        def catalog(self):
            return ()
        def to_pc_info(self, snapshot):
            return proto.pc_info()
    t = FakeTransport()
    w = DeviceWorker(t, Collector(), state=state, settle_seconds=0, max_rate=10000)
    w._connect()
    if failure == "collection error":
        frames.clear()
    elif failure == "missing":
        frames.append(TelemetrySnapshot({}, time.time()))
    else:
        invalid = replace(reading, sampled_at=1) if failure == "stale" else replace(reading, unit=failure)
        frames.append(TelemetrySnapshot({state.thermal_source: invalid}, time.time()))
    w._last_sample_time = None
    w._send_keepalive()
    w._send_keepalive()
    presets = [c[4] for c in t.calls if c[3] == proto.RES_PRESET]
    assert len(presets) == 2 and presets[-1] == proto.preset_payload_from_state(state)
    assert "thermal" in w.status().last_error.lower()


@pytest.mark.parametrize("pending", [False, True])
def test_config_writes_catalog_spelling_on_apply_and_reconnect(pending):
    t = CatalogTransport()
    desired = ScreenState(active_profile="case", media=(("MINE.PNG",),))
    w = DeviceWorker(t, lambda: proto.pc_info(), state=desired if pending else ScreenState(),
                     settle_seconds=0, max_rate=1000)
    w.start()
    try:
        _wait(lambda: w.status().connected)
        if not pending:
            assert w.submit(DeviceCommand.for_state(desired)).wait(1).applied
        configs = [c[4] for c in t.calls if c[3] == proto.RES_CONFIG]
        assert configs[-1]["waterBlockScreen"]["id"]["media"] == ["mine.png"]
    finally:
        w.stop()


def test_disconnected_delete_finishes_while_reopen_is_still_blocked():
    t = CatalogTransport()
    reopened, release = threading.Event(), threading.Event()
    def gated_open():
        if t.calls:
            reopened.set()
            release.wait(2)
    t.open = gated_open
    t.block_resource = "barrier"
    w = DeviceWorker(t, lambda: proto.pc_info(), settle_seconds=0, max_rate=1000)
    w.start()
    try:
        _wait(lambda: w.status().connected)
        w.submit(DeviceCommand(proto.POST, "barrier"))
        assert t.blocked.wait(1)
        command = DeviceCommand(proto.POST, proto.RES_MEDIA_DELETE, {"include": ["mine.png"]},
                                catalog_generation=w.status().catalog_generation, deadline=time.monotonic()+2)
        admitted = w.submit(command)
        w.notify_resume()
        t.release.set()
        assert reopened.wait(1)
        late = w.submit(command)
        assert admitted.done and not admitted.snapshot().applied
        assert late.done and not late.snapshot().queued
        assert not any(c[3] == proto.RES_MEDIA_DELETE for c in t.calls)
    finally:
        release.set()
        t.release.set()
        w.stop()
