# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace

import pytest

import ryuo_proto as proto
from ryuo_screen.device import DeviceCommand, plan_state_change
from ryuo_screen.store import ScreenState, SlotAssignment


def _slots(*widgets):
    result = []
    for index in range(6):
        if index < len(widgets):
            result.append(SlotAssignment(True, "sensor.{}".format(index), widgets[index]))
        else:
            result.append(SlotAssignment())
    return tuple(result)


def test_incremental_brightness_temperature_and_preset_do_not_restart_media():
    old = ScreenState(slots=_slots("CPU Temperature"))

    brightness = plan_state_change(old, replace(old, brightness=42))
    assert [command.resource for command in brightness.commands] == [proto.RES_BRIGHTNESS]
    assert brightness.commands[0].payload == {"value": 42}

    unit = plan_state_change(old, replace(old, temperature_unit="Fahrenheit"))
    assert [command.resource for command in unit.commands] == [proto.RES_TEMPERATURE]
    assert unit.commands[0].payload == {"value": "Fahrenheit"}

    visual = replace(
        old,
        slots=_slots("GPU Temperature", "Date&Time"),
        title_colors=("#112233",),
        content_colors=("#445566",),
        opacity=73,
    )
    preset = plan_state_change(old, visual)
    assert [command.resource for command in preset.commands] == [proto.RES_PRESET]
    assert preset.commands[0].payload["sysinfoDisplay"] == [
        "GPU Temperature", "Date&Time", "", "", "", ""
    ]
    assert preset.commands[0].payload["settings"]["filter"]["opacity"] == 73


def test_media_or_playback_change_is_one_coalesced_full_config():
    old = ScreenState()
    new = replace(
        old,
        media=(("clip.mp4",),),
        playback_modes=(proto.PLAY_CYCLE,),
        brightness=31,
        slots=_slots("CPU Temperature"),
    )
    plan = plan_state_change(old, new)
    assert plan.full_config is True
    assert len(plan.commands) == 1
    command = plan.commands[0]
    assert command.resource == proto.RES_CONFIG
    assert command.coalesce_key == "screen-state"
    assert command.payload["waterBlockScreen"]["brightness"] == 31
    assert command.payload["waterBlockScreen"]["id"]["media"] == ["clip.mp4"]


def test_screen_state_payload_supports_two_independent_zones():
    state = ScreenState(
        screen_mode=proto.MODE_SPLIT,
        media=(("a.mp4",), ("b.png",)),
        playback_modes=(proto.PLAY_CYCLE, proto.PLAY_RANDOM),
        title_colors=("#111111", "#222222"),
        content_colors=("#AAAAAA", "#BBBBBB"),
    )
    payload = proto.config_payload_from_state(state)
    screen = payload["waterBlockScreen"]["id"]
    assert screen["media"] == [["a.mp4"], ["b.png"]]
    assert screen["playMode"] == [proto.PLAY_CYCLE, proto.PLAY_RANDOM]
    assert len(screen["settings"]) == 2
    preset = proto.preset_payload_from_state(state)
    assert [item["titleColor"] for item in preset["settings"]] == [
        "#111111", "#222222"
    ]


def test_oversized_full_config_is_rejected_when_command_is_built():
    state = ScreenState(media=((tuple("{}-{}.mp4".format(i, "x" * 80) for i in range(30))),))
    with pytest.raises(ValueError, match="1024-byte report"):
        DeviceCommand.for_state(state).validated(seq=1)
