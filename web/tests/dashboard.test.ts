import {beforeAll, describe, expect, it} from "vitest";

import type {AppView} from "../src/store";
import type {SnapshotDocument} from "../src/api-types";

beforeAll(async () => {
  await import("../src/ui/dashboard-page");
});

const view = (snapshot: SnapshotDocument | null, phase: AppView["phase"] = "ready", error: string | null = null): AppView => ({
  phase,
  auth: {required: false, authenticated: true, csrfToken: null},
  csrfToken: null,
  snapshot,
  error,
  connected: true,
  lastEventId: 3,
  retryDelay: 500,
});

const dashboardSnapshot: SnapshotDocument = {
  revision: 9,
  state: {
    schema_version: 1,
    revision: 9,
    active_profile: "Miku Cycle",
    screen_mode: "Screen Splitting",
    media: [["Ryuo_IV_MIKU_WW_01.mp4"], ["custom.mp4"]],
    playback_modes: ["Cycle", "Single"],
    slots: Array.from({length: 6}, () => ({enabled: false, measurement_id: "", widget: "", label: null})),
    brightness: 73,
    temperature_unit: "Celsius",
    refresh_interval: 1,
    title_colors: ["#E5252B", "#E5252B"],
    content_colors: ["#FFFFFF", "#FFFFFF"],
    opacity: 100,
    rgb_mode: "off",
    rgb_target: "value",
    thermal_source: "cpu.temperature",
    sensor_selectors: {},
  },
  device: {
    connected: true,
    phase: "healthy",
    health: "healthy",
    model: "Ryuo IV Miku WW",
    firmware: "1.2.3",
    uptime: 3661,
    last_ack: 88,
    reconnect_count: 2,
  },
  telemetry: {
    sampledAt: 20,
    errors: {rapl: "permission denied"},
    measurements: {
      "cpu.temperature": {value: 64.2, unit: "°C", available: true, error: null, source: "/sys/cpu", sampledAt: 20},
      "gpu.temperature": {value: 71, unit: "°C", available: true, error: null, source: "/sys/gpu", sampledAt: 20},
      "gpu.vram.used": {value: 12_884_901_888, unit: "B", available: true, error: null, source: "/sys/vram", sampledAt: 20},
      "gpu.power": {value: null, unit: "W", available: false, error: "permission denied", source: "/sys/power", sampledAt: 20},
      "fan.cpu": {value: 1234, unit: "RPM", available: true, error: null, source: "/sys/fan", sampledAt: 20},
    },
  },
};

describe("dashboard-page", () => {
  it("renders device, screen and live telemetry with explicit unavailable reasons", async () => {
    const element = window.document.createElement("dashboard-page") as HTMLElement & {view: AppView; updateComplete: Promise<unknown>};
    element.view = view(dashboardSnapshot);
    window.document.body.append(element);
    await element.updateComplete;
    const text = element.shadowRoot?.textContent ?? "";
    expect(text).toContain("Ryuo IV Miku WW");
    expect(text).toContain("1.2.3");
    expect(text).toContain("Miku Cycle");
    expect(text).toContain("Screen Splitting");
    expect(text).toContain("73%");
    expect(text).toContain("64.2 °C");
    expect(text).toContain("71 °C");
    expect(text).toContain("12.0 GiB");
    expect(text).toContain("permission denied");
    expect(text).toContain("1234 RPM");
    expect(element.shadowRoot?.querySelector("main[aria-label='Сводка системы']")).not.toBeNull();
    expect(element.shadowRoot?.querySelector("section[aria-label='Телеметрия']")).not.toBeNull();
    element.remove();
  });

  it("renders loading and degraded states without hiding last good data", async () => {
    const element = window.document.createElement("dashboard-page") as HTMLElement & {view: AppView; updateComplete: Promise<unknown>};
    element.view = view(dashboardSnapshot, "error", "Live connection interrupted");
    window.document.body.append(element);
    await element.updateComplete;
    expect(element.shadowRoot?.textContent).toContain("Live connection interrupted");
    expect(element.shadowRoot?.textContent).toContain("Ryuo IV Miku WW");
    element.view = view(null, "loading");
    await element.updateComplete;
    expect(element.shadowRoot?.textContent).toContain("Загрузка");
    element.remove();
  });

  it("renders an actionable initial error instead of an endless loading state", async () => {
    const element = window.document.createElement("dashboard-page") as HTMLElement & {view: AppView; updateComplete: Promise<unknown>};
    element.view = view(null, "error", "API недоступен");
    window.document.body.append(element);
    await element.updateComplete;
    const alert = element.shadowRoot?.querySelector("[role='alert']");
    expect(alert?.textContent).toContain("API недоступен");
    expect(alert?.textContent).toContain("Повторите");
    expect(element.shadowRoot?.textContent).not.toContain("Загрузка телеметрии");
    element.remove();
  });
});
