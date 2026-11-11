import {describe, expect, it} from "vitest";

import type {ScreenStateDocument, SensorDescriptorDocument, SlotAssignment} from "../src/api-types";
import {
  disableSlot,
  normalizeSlots,
  reorderSlots,
  screenModeState,
  selectableSensors,
  serializePatch,
} from "../src/screen-model";

const empty = (measurementId = ""): SlotAssignment => ({
  enabled: Boolean(measurementId),
  measurement_id: measurementId,
  widget: measurementId,
  label: null,
});

const state = (): ScreenStateDocument => ({
  schema_version: 1,
  revision: 17,
  active_profile: null,
  screen_mode: "Full Screen",
  media: [["miku.mp4"]],
  playback_modes: ["Cycle"],
  slots: normalizeSlots([empty("cpu.temperature"), empty("gpu.temperature")]),
  brightness: 85,
  temperature_unit: "Celsius",
  refresh_interval: 1,
  title_colors: ["#E5252B"],
  content_colors: ["#FFFFFF"],
  opacity: 100,
  rgb_mode: "off",
  rgb_target: "value",
  thermal_source: "cpu.temperature",
  sensor_selectors: {},
});

const sensor = (
  measurementId: string,
  unit = "°C",
  available = true,
): SensorDescriptorDocument => ({
  ref: {provider: "linux", device: "pci-0000:01:00.0", channel: measurementId},
  measurementId,
  label: measurementId,
  unit,
  available,
  source: `/sys/${measurementId}`,
  metadata: {},
  error: available ? null : "permission denied",
});

describe("screen model", () => {
  it("always keeps exactly six stable positions and disables without reindexing", () => {
    const slots = normalizeSlots([empty("cpu.temperature"), empty("gpu.temperature")]);
    expect(slots).toHaveLength(6);
    const disabled = disableSlot(slots, 0);
    expect(disabled).toHaveLength(6);
    expect(disabled[0]).toMatchObject({enabled: false, measurement_id: "cpu.temperature"});
    expect(disabled[1].measurement_id).toBe("gpu.temperature");
    expect(() => normalizeSlots(Array.from({length: 7}, () => empty()))).toThrow(/six/i);
  });

  it("reorders slots without losing disabled positions", () => {
    const slots = normalizeSlots([empty("a"), empty("b"), empty("c")]);
    const moved = reorderSlots(slots, 0, 2);
    expect(moved.map((slot) => slot.measurement_id)).toEqual(["b", "c", "a", "", "", ""]);
    expect(moved).toHaveLength(6);
  });

  it("switches full/split layout with valid independent zone arrays", () => {
    const split = screenModeState(state(), "Screen Splitting");
    expect(split.media).toEqual([["miku.mp4"], []]);
    expect(split.playback_modes).toEqual(["Cycle", "Single"]);
    expect(split.title_colors).toHaveLength(2);
    const full = screenModeState(split, "Full Screen");
    expect(full.media).toEqual([["miku.mp4"]]);
    expect(full.content_colors).toHaveLength(1);
  });

  it("excludes unsupported measurements and marks fan user-label capability", () => {
    const options = selectableSensors([
      sensor("cpu.temperature"),
      sensor("gpu.vram.used", "B"),
      sensor("fan.aio.rpm", "RPM", false),
    ]);
    expect(options.map((item) => item.descriptor.measurementId)).toEqual([
      "cpu.temperature",
      "fan.aio.rpm",
    ]);
    expect(options[1]).toMatchObject({userLabelCapable: true, available: false});
    expect(options[0].userLabelCapable).toBe(false);
  });

  it("serializes only changed fields while retaining the current revision", () => {
    expect(serializePatch(state(), {brightness: 42})).toEqual({revision: 17, brightness: 42});
  });
});
