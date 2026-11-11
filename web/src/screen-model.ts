import type {
  ScreenStateDocument,
  SensorDescriptorDocument,
  SlotAssignment,
} from "./api-types";

export const SLOT_COUNT = 6;

const emptySlot = (): SlotAssignment => ({
  enabled: false,
  measurement_id: "",
  widget: "",
  label: null,
});

const cloneSlot = (slot: SlotAssignment): SlotAssignment => ({...slot});

export const normalizeSlots = (slots: readonly SlotAssignment[]): SlotAssignment[] => {
  if (slots.length > SLOT_COUNT) throw new RangeError("screen editor supports exactly six slots");
  const normalized = slots.map(cloneSlot);
  while (normalized.length < SLOT_COUNT) normalized.push(emptySlot());
  return normalized;
};

export const disableSlot = (
  slots: readonly SlotAssignment[],
  index: number,
): SlotAssignment[] => normalizeSlots(slots).map((slot, position) => position === index
  ? {...slot, enabled: false}
  : slot);

export const reorderSlots = (
  slots: readonly SlotAssignment[],
  from: number,
  to: number,
): SlotAssignment[] => {
  const normalized = normalizeSlots(slots);
  if (!Number.isInteger(from) || !Number.isInteger(to)
      || from < 0 || from >= SLOT_COUNT || to < 0 || to >= SLOT_COUNT) {
    throw new RangeError("slot position must be between zero and five");
  }
  const [moved] = normalized.splice(from, 1);
  normalized.splice(to, 0, moved);
  return normalized;
};

const firstOr = <T>(values: readonly T[], fallback: T): T => values[0] ?? fallback;

export const screenModeState = (
  state: ScreenStateDocument,
  screenMode: "Full Screen" | "Screen Splitting",
): ScreenStateDocument => {
  if (screenMode === "Screen Splitting") {
    return {
      ...state,
      screen_mode: screenMode,
      media: [[...(state.media[0] ?? [])], [...(state.media[1] ?? [])]],
      playback_modes: [
        firstOr(state.playback_modes, "Single"),
        state.playback_modes[1] ?? "Single",
      ],
      title_colors: [firstOr(state.title_colors, "#E5252B"), state.title_colors[1] ?? firstOr(state.title_colors, "#E5252B")],
      content_colors: [firstOr(state.content_colors, "#FFFFFF"), state.content_colors[1] ?? firstOr(state.content_colors, "#FFFFFF")],
    };
  }
  return {
    ...state,
    screen_mode: "Full Screen",
    media: [[...(state.media[0] ?? [])]],
    playback_modes: [firstOr(state.playback_modes, "Single")],
    title_colors: [firstOr(state.title_colors, "#E5252B")],
    content_colors: [firstOr(state.content_colors, "#FFFFFF")],
  };
};

const WIDGETS: Readonly<Record<string, string>> = Object.freeze({
  "cpu.load": "CPU Load",
  "cpu.usage": "CPU Usage",
  "cpu.temperature": "CPU Temperature",
  "cpu.frequency": "CPU Speed Average",
  "cpu.voltage": "CPU Voltage",
  "gpu.load": "GPU Load",
  "gpu.usage": "GPU Usage",
  "gpu.temperature": "GPU Temperature",
  "gpu.frequency": "GPU Speed",
  "gpu.power": "GPU Power",
  "gpu.voltage": "GPU Voltage",
  "memory.load": "Memory Utilization",
  "memory.frequency": "Memory Frequency",
  "disk.temperature": "Hard Disk Temperature",
  "motherboard.temperature": "Motherboard Temperature",
});

export interface SelectableSensor {
  descriptor: SensorDescriptorDocument;
  widget: string;
  available: boolean;
  userLabelCapable: boolean;
}

export const selectableSensors = (
  descriptors: readonly SensorDescriptorDocument[],
): SelectableSensor[] => descriptors.flatMap((descriptor) => {
  const fan = descriptor.measurementId.startsWith("fan.") && descriptor.unit === "RPM";
  const widget = fan
    ? `Fan Speed ${descriptor.label}`
    : WIDGETS[descriptor.measurementId];
  if (!widget) return [];
  return [{
    descriptor,
    widget,
    available: descriptor.available,
    userLabelCapable: fan,
  }];
});

export const serializePatch = (
  state: ScreenStateDocument,
  changes: Record<string, unknown>,
): Record<string, unknown> => ({revision: state.revision, ...changes});

export const cloneScreenState = (state: ScreenStateDocument): ScreenStateDocument => ({
  ...state,
  media: state.media.map((zone) => [...zone]),
  playback_modes: [...state.playback_modes],
  slots: normalizeSlots(state.slots),
  title_colors: [...state.title_colors],
  content_colors: [...state.content_colors],
  sensor_selectors: {...state.sensor_selectors},
});
