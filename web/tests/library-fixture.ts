import {afterEach, vi} from "vitest";
import {ApiClient} from "../src/api";
import type {ScreenStateDocument, SensorDescriptorDocument, SensorRefDocument} from "../src/api-types";
import {AppStore} from "../src/store";

export const filename = "Ryuo_IV_MIKU_WW_01.mp4";
export const state: ScreenStateDocument = {
  schema_version: 1, revision: 4, active_profile: "miku-cycle",
  screen_mode: "Screen Splitting", media: [[filename, "user-one.mp4"], ["user-one.mp4", filename]],
  playback_modes: ["Cycle", "Single"], slots: Array.from({length: 6}, () =>
    ({enabled: false, measurement_id: "", widget: "", label: null})),
  brightness: 85, temperature_unit: "Celsius", refresh_interval: 1,
  title_colors: ["#E5252B", "#E5252B"], content_colors: ["#FFFFFF", "#FFFFFF"],
  opacity: 100, rgb_mode: "off", rgb_target: "value", thermal_source: "cpu.temperature", sensor_selectors: {},
};
const {revision: _revision, active_profile: _active, ...configuration} = state;
export const profiles = [
  ...[1, 2, 3, 4].map((n) => ({
    ...configuration, slug: `miku-single-0${n}`, name: `Miku Single 0${n}`, factory: true,
  })),
  {...configuration, slug: "miku-cycle", name: "Miku Cycle", factory: true},
  {...configuration, slug: "custom", name: "My Profile", factory: false},
];

const gpuRef = {provider: "amd", device: "0000:08:00.0", channel: "gpu.load"};
const boardRef = {provider: "hwmon", device: "platform/nct6775.656/nct6799", channel: "temp2"};
const sensor = (ref: SensorRefDocument, measurementId: string, source: string): SensorDescriptorDocument => ({
  ref, measurementId, label: measurementId, available: true, unit: "°C", source, metadata: {}, error: null,
});

export const security = {
  bindMode: "lan", lanEnabled: true, authenticationRequired: true, trustedProxyCount: 1,
  sessions: {active: 1, capacity: 5},
};

export const json = (body: unknown, status = 200): Response => Response.json(body, {status});
export const mutation = {revision: 5, saved: true, queued: true, applied: false, acked: false, error: null};

export async function setup(
  handle: (path: string, init: RequestInit) => Response | undefined = () => undefined,
  available = true,
) {
  const store = new AppStore(new ApiClient(), {connect: () => ({close() {}})});
  const requests: {path: string; init: RequestInit}[] = [];
  vi.stubGlobal("fetch", async (path: string, init: RequestInit) => {
    requests.push({path, init});
    const response = handle(path, init);
    if (response) return response;
    switch (path) {
      case "/api/v1/auth/status":
        return json({required: true, authenticated: true, csrfToken: "secret", expiresIn: 60});
      case "/api/v1/state": return json({revision: 4, state});
      case "/api/v1/device": return json({connected: true, health: "healthy", serial: "device-secret"});
      case "/api/v1/telemetry": return json({sampledAt: 5, errors: {}, measurements: {
        "gpu.load": {ref: gpuRef, source: "gpu_busy_percent", value: 30, unit: "%", available: true},
      }});
      case "/api/v1/sensors": return json({sensors: [
        sensor(gpuRef, "gpu.load", "gpu_busy_percent"), sensor(boardRef, "motherboard.temperature", "temp2_input"),
      ], error: null});
      case "/api/v1/media": return json({
        factory: [filename], custom: ["user-one.mp4"],
        tools: {ffprobe: true, ffmpeg: available},
        adb: {available, reason: available ? null : "ADB not available", serial: "adb-sensitive-serial", targetToken: available ? "observed-cooler" : undefined},
      });
      case "/api/v1/profiles": return json({profiles});
      case "/api/v1/diagnostics": return json({security, session: {required: true, authenticated: true, expiresIn: 58}});
      default: return json({error: "not_found", message: path}, 404);
    }
  });
  await store.start();
  return {store, requests};
}

export const get = <T extends HTMLElement>(root: ParentNode, selector: string) => root.querySelector<T>(selector)!;
export const click = (root: ParentNode, selector: string) => get<HTMLButtonElement>(root, selector).click();
export function change(root: ParentNode, selector: string, value: string, type = "change") {
  const input = get<HTMLInputElement>(root, selector);
  input.value = value;
  input.dispatchEvent(new Event(type, {bubbles: true}));
}
export async function render<T extends HTMLElement & {updateComplete: Promise<unknown>}>(
  page: T, store: AppStore,
): Promise<ShadowRoot> {
  const unsubscribe = store.subscribe((view) => Object.assign(page, {view, store}));
  cleanup.push(() => {unsubscribe(); store.stop();});
  document.body.append(page);
  await page.updateComplete;
  return page.shadowRoot!;
}
const cleanup: (() => void)[] = [];
afterEach(() => {
  document.body.replaceChildren();
  cleanup.splice(0).forEach((dispose) => dispose());
  vi.unstubAllGlobals();
});
