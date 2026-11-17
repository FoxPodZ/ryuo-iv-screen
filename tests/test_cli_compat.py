# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sys

import pytest

import ryuo_ctl
import ryuo_send
from test_client import unix_http


def _argv(monkeypatch, script, *parts):
    monkeypatch.setattr(sys, "argv", [script + ".py", *map(str, parts)])


@pytest.fixture
def no_hid(monkeypatch):
    def fail(*_args):
        pytest.fail("CLI attempted to open HID")

    monkeypatch.setattr(ryuo_ctl, "open_dev", fail)
    monkeypatch.setattr(ryuo_send, "open_device", fail)
    monkeypatch.setitem(sys.modules, "hid", None)


@pytest.fixture
def fake_ctl(monkeypatch):
    calls = []

    class Handle:
        def close(self):
            calls.append(("close",))

    def open_dev(*args):
        calls.append(("open",) + args)
        return Handle()

    def transact(_handle, method, resource, payload=None, **_kwargs):
        calls.append((method, resource, payload))
        return ('HTTP/1.1 200 OK\r\n\r\n'
                '{"serial":"SECRET","media":{"custom":["mine.png"],"preset":["RYUO.png"]}}')

    monkeypatch.setattr(ryuo_ctl, "open_dev", open_dev)
    monkeypatch.setattr(ryuo_ctl, "txn", transact)
    return calls


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["get"], ("GET", "config", None)),
        (["get", "spec"], ("GET", "spec", None)),
        (["brightness", "30"], ("POST", "brightness", {"value": 30})),
        (["items", "CPU Load", "Date&Time"],
         ("POST", "sysinfoDisplay", {"items": ["CPU Load", "Date&Time"]})),
        (["info"], ("POST", "conn", None)),
        (["ls"], ("POST", "conn", None)),
        (["rm", "mine.png"], ("POST", "mediaDelete", {"include": ["mine.png"]})),
        (["rm", "--except", "keep.png"], ("POST", "mediaDelete", {"exclude": ["keep.png"]})),
        (["raw", "POST", "temperature", '{"value":"Celsius"}'],
         ("POST", "temperature", {"value": "Celsius"})),
    ],
)
def test_direct_ctl_keeps_legacy_parser_wire_commands_and_listing(
    monkeypatch, tmp_path, fake_ctl, capsys, command, expected
):
    _argv(monkeypatch, "ryuo_ctl", "--direct", "--socket", tmp_path / "missing",
          "--vid", "0x1c75", "--pid", "0x1c76", "--index", "1", *command)
    ryuo_ctl.main()
    assert fake_ctl == [("open", 0x1C75, 0x1C76, 1), expected, ("close",)]
    output = capsys.readouterr().out
    if command == ["ls"]:
        assert output == "custom (1):\n  mine.png\npreset (1):\n  RYUO.png\n"
    if command == ["info"]:
        assert "SECRET" not in output


def test_absent_service_falls_back_to_legacy_direct(monkeypatch, tmp_path, fake_ctl):
    _argv(monkeypatch, "ryuo_ctl", "--socket", tmp_path / "missing", "brightness", "30")
    ryuo_ctl.main()
    assert fake_ctl == [("open", None, 0x1C76, None),
                        ("POST", "brightness", {"value": 30}), ("close",)]


@pytest.mark.parametrize("command", [["--direct", "brightness", "30"],
                                     ["raw", "GET", "config"], ["get", "spec"],
                                     ["--pid", "0x1c76", "brightness", "30"],
                                     ["info", "--serial"]])
def test_active_listener_refuses_direct_without_opening_hid(
    monkeypatch, unix_http, no_hid, command
):
    path, calls, _ = unix_http
    _argv(monkeypatch, "ryuo_ctl", "--socket", path, *command)
    with pytest.raises(SystemExit, match="stop"):
        ryuo_ctl.main()
    assert calls == []


@pytest.mark.skipif(sys.platform != "linux", reason="Linux HID process claim")
def test_other_owner_prevents_fallback_even_with_missing_socket(
    monkeypatch, tmp_path, no_hid
):
    from ryuo_screen.ownership import DeviceOwnership

    with DeviceOwnership():
        _argv(monkeypatch, "ryuo_ctl", "--socket", tmp_path / "missing", "get")
        with pytest.raises(SystemExit, match="owner"):
            ryuo_ctl.main()


@pytest.mark.parametrize("command", [
    ["raw", "POST", "upgrade"],
    ["raw", "POST", "transport", '{"type":"firmware"}'],
])
def test_direct_raw_preserves_existing_denylist(monkeypatch, tmp_path, fake_ctl, command):
    _argv(monkeypatch, "ryuo_ctl", "--socket", tmp_path / "missing", *command)
    with pytest.raises(SystemExit, match="refusing"):
        ryuo_ctl.main()
    assert fake_ctl == [("open", None, 0x1C76, None), ("close",)]


def test_service_brightness_routes_without_hid_and_reports_queued_truthfully(
    monkeypatch, unix_http, no_hid, capsys
):
    from ryuo_screen.ownership import DeviceOwnership

    path, calls, responses = unix_http
    result = {"revision": 6, "saved": True, "queued": True, "applied": False,
              "acked": False, "error": None}
    responses.extend([(200, {"revision": 5, "state": {}}), (200, result)])
    _argv(monkeypatch, "ryuo_ctl", "--socket", path, "brightness", "30")
    with DeviceOwnership():
        ryuo_ctl.main()
    assert calls == [("GET", "/api/v1/state", None),
                     ("PATCH", "/api/v1/brightness", {"revision": 5, "brightness": 30})]
    assert json.loads(capsys.readouterr().out) == result


def test_revision_conflict_never_falls_back_to_direct(
    monkeypatch, unix_http, no_hid
):
    path, calls, responses = unix_http
    responses.extend([
        (200, {"revision": 5, "state": {}}),
        (409, {"error": "revision_conflict", "message": "revision changed", "currentRevision": 6}),
    ])
    _argv(monkeypatch, "ryuo_ctl", "--socket", path, "brightness", "30")
    with pytest.raises(SystemExit, match="revision changed"):
        ryuo_ctl.main()
    assert len(calls) == 2


def test_service_media_except_deletes_only_listed_custom(
    monkeypatch, unix_http, no_hid
):
    path, calls, responses = unix_http
    responses.extend([
        (200, {"custom": ["keep.png", "with space.png", "RYUO.png"],
               "factory": ["RYUO.png"]}),
        (200, {"name": "with space.png", "applied": True, "confirmed": True, "error": None}),
    ])
    _argv(monkeypatch, "ryuo_ctl", "--socket", path, "rm", "--except", "keep.png")
    ryuo_ctl.main()
    assert calls == [("GET", "/api/v1/media", None),
                     ("DELETE", "/api/v1/media/with%20space.png", None)]


@pytest.mark.parametrize("script", [ryuo_ctl, ryuo_send])
def test_list_keeps_enumeration_and_does_not_claim(monkeypatch, capsys, script):
    from types import SimpleNamespace
    from ryuo_screen.ownership import DeviceOwnership

    def enumerate_hid(vid, pid):
        assert (vid, pid) == (0x1C75, 0x1C76)
        return [{"usage_page": 0xFF00, "interface_number": 1, "product_string": "Ryuo"}]

    monkeypatch.setitem(sys.modules, "hid", SimpleNamespace(enumerate=enumerate_hid))
    _argv(monkeypatch, script.__name__, "--vid", "0x1c75", "--pid", "0x1c76", "--list")
    with DeviceOwnership():
        script.main()
    assert capsys.readouterr().out == "[0] usage_page=0xff00 iface=1 product='Ryuo'\n"


def test_send_direct_config_only_keeps_wire_config_output_and_closes_handle(
    monkeypatch, tmp_path, capsys,
):
    calls = []

    class Handle:
        def close(self):
            calls.append("close")

    def open_handle(vid, pid, index):
        assert (vid, pid, index) == (None, 0x1C76, 2)
        return Handle()

    def txn(_handle, method, resource, payload, seq, **_kwargs):
        assert (method, resource, seq) == ("POST", "config", 1)
        calls.append(payload)

    monkeypatch.setattr(ryuo_send, "open_device", open_handle)
    monkeypatch.setattr(ryuo_send, "txn", txn)
    monkeypatch.setattr(ryuo_send, "_nvidia", lambda: {"name": "Test GPU"})
    monkeypatch.setattr(ryuo_send, "_cpu_name", lambda: "Test CPU")
    monkeypatch.setattr(ryuo_send.time, "sleep", lambda _seconds: None)
    _argv(monkeypatch, "ryuo_send", "--socket", tmp_path / "missing",
          "--direct", "--index", 2, "--config-only", "--brightness", 33,
          "--timezone", "Europe/Moscow", "--items", "Date&Time")
    ryuo_send.main()
    assert calls[1:] == ["close"]
    config = calls[0]
    assert config["waterBlockScreen"]["brightness"] == 33
    assert config["waterBlockScreen"]["id"]["timeZone"] == "Europe/Moscow"
    assert "config pushed: slots=['Date&Time', '', '', '', '', ''] brightness=33" \
        in capsys.readouterr().out


def test_send_service_applies_split_config_with_current_revisions(
    monkeypatch, unix_http, no_hid, capsys
):
    path, calls, responses = unix_http
    for revision in range(5, 8):
        responses.extend([
            (200, {"revision": revision, "state": {}}),
            (200, {"revision": revision + 1, "saved": True, "queued": True,
                   "applied": False, "acked": False, "error": None}),
        ])
    _argv(monkeypatch, "ryuo_send", "--socket", path, "--config-only",
          "--media", "a.mp4", "--media2", "b.png", "--shuffle", "--play-mode2", "Cycle",
          "--title-color", "#AA0000", "--title-color2", "#00BB00",
          "--content-color", "#FFFFFF", "--content-color2", "#0000CC",
          "--screen-mode", "Screen Splitting", "--opacity", "80",
          "--items", "CPU Load", "Date&Time", "--rgb", "both", "--rgb-mode", "thermal",
          "--rgb-source", "gpu", "--brightness", "25", "--unit", "Fahrenheit",
          "--interval", "2", "-v")
    ryuo_send.main()
    assert [(method, uri, body.get("revision") if body else None)
            for method, uri, body in calls] == [
        ("GET", "/api/v1/state", None), ("PATCH", "/api/v1/screen", 5),
        ("GET", "/api/v1/state", None), ("PATCH", "/api/v1/brightness", 6),
        ("GET", "/api/v1/state", None), ("PATCH", "/api/v1/telemetry-settings", 7),
    ]
    screen = calls[1][2]
    assert screen["screen_mode"] == "Screen Splitting"
    assert screen["media"] == [["a.mp4"], ["b.png"]]
    assert screen["playback_modes"] == ["Random", "Cycle"]
    assert screen["title_colors"] == ["#AA0000", "#00BB00"]
    assert screen["content_colors"] == ["#FFFFFF", "#0000CC"]
    assert screen["rgb_mode"] == "thermal"
    assert screen["rgb_target"] == "both"
    assert screen["thermal_source"] == "gpu.temperature"
    assert screen["slots"][0]["widget"] == "CPU Load"
    assert screen["slots"][1]["widget"] == "Date&Time"
    assert len(screen["slots"]) == 6
    assert calls[3][2]["brightness"] == 25
    assert calls[5][2] == {"revision": 7, "temperature_unit": "Fahrenheit", "refresh_interval": 2.0}
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [result["revision"] for result in results] == [6, 7, 8]
    assert [result["operation"] for result in results] == ["screen", "brightness", "telemetry-settings"]
    assert all(not result["applied"] and not result["acked"] for result in results)


@pytest.mark.parametrize("status", [200, 409])
def test_send_stops_after_later_error_and_identifies_completed_mutation(
    monkeypatch, unix_http, no_hid, capsys, status,
):
    path, calls, responses = unix_http
    first_result = {"revision": 6, "saved": True, "queued": True,
                    "applied": False, "acked": False, "error": None}
    later_result = {"revision": 7, "saved": True, "queued": False,
                    "applied": False, "acked": False, "error": "worker unavailable"}
    if status == 409:
        later_result = {"error": "revision_conflict", "message": "revision changed",
                        "currentRevision": 8}
    responses.extend([
        (200, {"revision": 5, "state": {}}), (200, first_result),
        (200, {"revision": 6, "state": {}}), (status, later_result),
    ])
    _argv(monkeypatch, "ryuo_send", "--socket", path)
    with pytest.raises(SystemExit, match="worker unavailable|revision changed"):
        ryuo_send.main()
    assert [uri for _, uri, _ in calls] == [
        "/api/v1/state", "/api/v1/screen", "/api/v1/state", "/api/v1/brightness"
    ]
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert results[0] == dict(first_result, operation="screen")
    if status == 200:
        assert results[1] == dict(later_result, operation="brightness")


def test_send_unsupported_option_rejects_before_api_mutation(
    monkeypatch, unix_http, no_hid,
):
    path, calls, _ = unix_http
    _argv(monkeypatch, "ryuo_send", "--socket", path, "--readout", "Coolant=1234")
    with pytest.raises(SystemExit, match="stop"):
        ryuo_send.main()
    assert calls == []
