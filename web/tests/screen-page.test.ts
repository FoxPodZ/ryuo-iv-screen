import {afterEach, describe, expect, it, vi} from "vitest";

import type {SensorDescriptorDocument, SnapshotDocument} from "../src/api-types";
import type {ScreenController} from "../src/ui/screen-page";
import "../src/ui/screen-page";
import type {ScreenPage} from "../src/ui/screen-page";

const sensors: SensorDescriptorDocument[] = [
  {
    ref: {provider: "cpu", device: "package-0", channel: "temp1"},
    measurementId: "cpu.temperature",
    label: "CPU Tdie",
    unit: "°C",
    available: true,
    source: "/sys/class/hwmon/hwmon4/temp1_input",
    metadata: {},
    error: null,
  },
  {
    ref: {provider: "hwmon", device: "nct6799", channel: "fan2"},
    measurementId: "fan.aio.rpm",
    label: "AIO Pump",
    unit: "RPM",
    available: false,
    source: "/sys/devices/platform/nct6799/fan2_input",
    metadata: {},
    error: "permission denied",
  },
];

const snapshot = (): SnapshotDocument => ({
  revision: 4,
  state: {
    schema_version: 1,
    revision: 4,
    active_profile: "miku-cycle",
    screen_mode: "Full Screen",
    media: [["Ryuo_IV_MIKU_WW_01.mp4"]],
    playback_modes: ["Cycle"],
    slots: [
      {enabled: true, measurement_id: "cpu.temperature", widget: "CPU Temperature", label: null},
      {enabled: true, measurement_id: "fan.aio.rpm", widget: "Fan Speed AIO Pump", label: "AIO Pump"},
      ...Array.from({length: 4}, () => ({enabled: false, measurement_id: "", widget: "", label: null})),
    ],
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
  },
  device: {connected: true, health: "healthy"},
  telemetry: {sampledAt: 1, measurements: {}, errors: {}},
});

class FakeController implements ScreenController {
  readonly calls: Array<{kind: string; changes: Record<string, unknown>}> = [];
  async ensureSensors(): Promise<void> {}
  async patchScreen(kind: string, changes: Record<string, unknown>): Promise<void> {
    this.calls.push({kind, changes});
  }
}

const renderPage = async (controller = new FakeController()): Promise<{page: ScreenPage; controller: FakeController}> => {
  const page = document.createElement("screen-page") as ScreenPage;
  page.snapshot = snapshot();
  page.sensors = sensors;
  page.controller = controller;
  document.body.append(page);
  await page.updateComplete;
  return {page, controller};
};

afterEach(() => {
  vi.useRealTimers();
  document.body.replaceChildren();
});

describe("screen-page", () => {
  it("renders an honest full/split preview and six accessible slots", async () => {
    const {page} = await renderPage();
    expect(page.shadowRoot?.textContent).toContain("Предпросмотр конфигурации — не снимок экрана");
    expect(page.shadowRoot?.textContent?.toLowerCase()).not.toContain("live screenshot");
    const slots = page.shadowRoot?.querySelectorAll("sensor-slot") ?? [];
    expect(slots).toHaveLength(6);
    expect(slots[0].getAttribute("aria-label")).toContain("Слот 1");
    expect(page.shadowRoot?.textContent).toContain("permission denied");
    expect(page.shadowRoot?.textContent).toContain("nct6799");
  });

  it("mouse drag and keyboard move produce the same slot order", async () => {
    const keyboard = await renderPage();
    const first = keyboard.page.shadowRoot?.querySelector("sensor-slot") as HTMLElement;
    first.dispatchEvent(new CustomEvent("slot-move", {detail: {from: 0, to: 1}, bubbles: true, composed: true}));
    await keyboard.page.updateComplete;
    const keyboardOrder = keyboard.page.draft.slots.map((item) => item.measurement_id);

    const mouse = await renderPage();
    const mouseSlots = mouse.page.shadowRoot?.querySelectorAll("sensor-slot") ?? [];
    mouseSlots[0].dispatchEvent(new CustomEvent("slot-drag-start", {detail: {index: 0}, bubbles: true, composed: true}));
    mouseSlots[1].dispatchEvent(new CustomEvent("slot-drop", {detail: {index: 1}, bubbles: true, composed: true}));
    await mouse.page.updateComplete;
    expect(mouse.page.draft.slots.map((item) => item.measurement_id)).toEqual(keyboardOrder);
  });

  it("bounds controls and coalesces incremental endpoint patches", async () => {
    vi.useFakeTimers();
    const {page, controller} = await renderPage();
    const brightness = page.shadowRoot?.querySelector<HTMLInputElement>('input[name="brightness"]');
    expect(brightness?.min).toBe("0");
    expect(brightness?.max).toBe("102");
    brightness!.value = "102";
    brightness!.dispatchEvent(new Event("input", {bubbles: true, composed: true}));
    brightness!.value = "55";
    brightness!.dispatchEvent(new Event("input", {bubbles: true, composed: true}));

    const opacity = page.shadowRoot?.querySelector<HTMLInputElement>('input[name="opacity"]');
    opacity!.value = "73";
    opacity!.dispatchEvent(new Event("input", {bubbles: true, composed: true}));
    expect(controller.calls).toEqual([]);
    await vi.advanceTimersByTimeAsync(180);
    expect(controller.calls).toEqual([
      {kind: "brightness", changes: {brightness: 55}},
      {kind: "screen", changes: {opacity: 73}},
    ]);
  });

  it("renders unit, interval, zone colors, RGB controls and only warns for full-config changes", async () => {
    const {page} = await renderPage();
    for (const name of ["temperature_unit", "refresh_interval", "title_color_0", "content_color_0", "opacity", "rgb_mode", "rgb_target", "thermal_source"]) {
      expect(page.shadowRoot?.querySelector(`[name="${name}"]`), name).not.toBeNull();
    }
    expect(page.shadowRoot?.querySelector("[data-full-restart]")).toBeNull();
    const mode = page.shadowRoot?.querySelector<HTMLSelectElement>('select[name="screen_mode"]');
    mode!.value = "Screen Splitting";
    mode!.dispatchEvent(new Event("change", {bubbles: true, composed: true}));
    await page.updateComplete;
    expect(page.shadowRoot?.querySelector("[data-full-restart]")?.textContent).toMatch(/перезапустит/i);
  });

  it("shows a revision conflict supplied by the store instead of overwriting", async () => {
    const page = document.createElement("screen-page") as ScreenPage;
    page.snapshot = snapshot();
    page.sensors = sensors;
    page.controller = new FakeController();
    page.mutationError = "Конфликт ревизий: загружено актуальное состояние";
    document.body.append(page);
    await page.updateComplete;
    expect(page.shadowRoot?.querySelector('[role="alert"]')?.textContent).toContain("Конфликт ревизий");
  });

  it("does not erase an in-progress draft when live telemetry keeps the same revision", async () => {
    const {page} = await renderPage();
    const brightness = page.shadowRoot?.querySelector<HTMLInputElement>('input[name="brightness"]');
    brightness!.value = "41";
    brightness!.dispatchEvent(new Event("input", {bubbles: true, composed: true}));
    page.snapshot = {...snapshot(), telemetry: {sampledAt: 2, measurements: {}, errors: {}}};
    await page.updateComplete;
    expect(page.draft.brightness).toBe(41);
  });
});
