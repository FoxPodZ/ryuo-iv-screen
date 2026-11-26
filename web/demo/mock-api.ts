// SPDX-License-Identifier: GPL-3.0-or-later
import type {Plugin} from "vite";
import type {ScreenStateDocument, SensorDescriptorDocument} from "../src/api-types";
import {configurationFromState} from "../src/profile-model.ts";

const sampledAt = 1_767_225_600;
const factory = [1, 2, 3, 4].map(n => `Ryuo_IV_MIKU_WW_0${n}.mp4`);
const custom = ["aurora.mp4", "nebula.png"];

function reading(measurementId: string, label: string, unit: string, value: number | null,
  provider: string, device: string, source: string, error: string | null = null) {
  const ref = {provider, device, channel: measurementId};
  const sensor: SensorDescriptorDocument = {measurementId, label, unit, ref, source,
    available: value !== null, error, metadata: {}};
  return {sensor, measurement: {value, unit, sampledAt, available: sensor.available, source, ref, error}};
}

const readings = [
  reading("cpu.temperature", "CPU Temperature", "°C", 62.5, "cpu", "Ryzen 9 7900X", "k10temp · Tctl"),
  reading("gpu.temperature", "GPU Temperature", "°C", 58, "amd", "RX 7900 XTX", "amdgpu · edge"),
  reading("gpu.vram.used", "VRAM", "B", 8.5 * 1024 ** 3, "amd", "RX 7900 XTX", "mem_info_vram_used"),
  reading("gpu.power", "GPU Power", "W", 184, "amd", "RX 7900 XTX", "power1_average"),
  reading("fan.cpu", "CPU fan", "RPM", 940, "hwmon", "NCT6799", "fan1_input"),
  reading("cpu.load", "CPU Load", "%", 36, "cpu", "Ryzen 9 7900X", "proc/stat"),
  reading("gpu.load", "GPU Load", "%", 68, "amd", "RX 7900 XTX", "gpu_busy_percent"),
  reading("cpu.power", "CPU Power", "W", null, "cpu", "Ryzen 9 7900X", "powercap", "Нет счётчика энергии"),
];
const sensors = readings.map(({sensor}) => sensor);
const telemetry = {sampledAt, measurements: Object.fromEntries(readings.map(({sensor, measurement}) =>
  [sensor.measurementId, measurement])), errors: {"cpu.power": "Нет счётчика энергии"}};

const state: ScreenStateDocument = {
  schema_version: 1, revision: 7, active_profile: "aurora-split", screen_mode: "Screen Splitting",
  media: [[factory[0]], [custom[0]]], playback_modes: ["Single", "Single"],
  slots: [
    ["cpu.temperature", "CPU Temperature"], ["cpu.load", "CPU Load"], ["fan.cpu", "Fan Speed CPU fan"],
    ["gpu.temperature", "GPU Temperature"], ["gpu.load", "GPU Load"], ["gpu.power", "GPU Power"],
  ].map(([measurement_id, widget]) => ({enabled: true, measurement_id, widget,
    label: measurement_id === "fan.cpu" ? "CPU fan" : null})),
  brightness: 85, temperature_unit: "Celsius", refresh_interval: 1, opacity: 100,
  title_colors: ["#65E5D7", "#F265A1"], content_colors: ["#FFFFFF", "#FFFFFF"],
  rgb_mode: "off", rgb_target: "value", thermal_source: "cpu.temperature", sensor_selectors: {},
};
const device = {connected: true, phase: "healthy", health: "healthy", model: "ROG Ryuo IV",
  firmware: "1.0.7", uptime: 8_220, last_ack: 42, reconnect_count: 0};
const snapshot = {demo: true, revision: state.revision, state, device, telemetry};
const configuration = configurationFromState(state);
const factoryConfiguration = {...configuration, screen_mode: "Full Screen",
  slots: Array.from({length: 6}, () => ({enabled: false, measurement_id: "", widget: "", label: null})),
  title_colors: ["#E5252B"], content_colors: ["#FFFFFF"]};
const profiles = [
  ...factory.map((filename, index) => ({...factoryConfiguration, factory: true,
    slug: `miku-single-0${index + 1}`, name: `Miku Single 0${index + 1}`,
    media: [[filename]], playback_modes: ["Single"]})),
  {...factoryConfiguration, factory: true, slug: "miku-cycle", name: "Miku Cycle",
    media: [factory], playback_modes: ["Cycle"]},
  {...configuration, factory: false, slug: "aurora-split", name: "Aurora Split"},
];

const resources: Record<string, object> = {
  "/auth/status": {required: false, authenticated: true, csrfToken: null},
  "/state": {revision: state.revision, state}, "/device": device, "/telemetry": telemetry,
  "/sensors": {sensors, error: null}, "/profiles": {profiles},
  "/media": {factory, custom, tools: {ffprobe: true, ffmpeg: true},
    adb: {available: false, reason: "Устройство отключено в деморежиме."}},
  "/diagnostics": {security: {bindMode: "loopback", lanEnabled: false, authenticationRequired: false,
    trustedProxyCount: 0, sessions: {active: 0, capacity: 10}}, session: {required: false, authenticated: true}},
};

export function demoApi(): Plugin {
  return {
    name: "ryuo-demo-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/api/v1", (request, response) => {
        const path = (request.url || "/").split("?")[0];
        response.setHeader("Cache-Control", "no-store");
        if (request.method === "GET" && path === "/events") {
          const previous = Number(request.headers["last-event-id"] ?? 0);
          const next = previous + 1;
          if (!Number.isSafeInteger(next) || next < 1) {
            response.writeHead(400, {"Content-Type": "application/json"});
            response.end(JSON.stringify({demo: true, error: "invalid_last_event_id"}));
            return;
          }
          response.writeHead(200, {"Content-Type": "text/event-stream"});
          response.write(`id: ${next}\nevent: snapshot\ndata: ${JSON.stringify(snapshot)}\n\n`);
          return; // Keep the fixed event visible until the browser disconnects.
        }
        response.setHeader("Content-Type", "application/json; charset=utf-8");
        if (request.method !== "GET") {
          response.statusCode = 405;
          response.setHeader("Allow", "GET");
          response.end(JSON.stringify({demo: true, error: "demo_read_only", message: "Деморежим доступен для просмотра."}));
          return;
        }
        const profile = profiles.find(item => path === `/profiles/${item.slug}/export`);
        if (profile) {
          response.setHeader("X-Ryuo-Demo", "true");
          response.end(JSON.stringify(profile));
          return;
        }
        const resource = resources[path];
        if (!resource) response.statusCode = 404;
        response.end(JSON.stringify({demo: true, ...(resource ?? {error: "not_found"})}));
      });
    },
  };
}
