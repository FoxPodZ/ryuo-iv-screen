// @vitest-environment node
import {afterAll, beforeAll, expect, it, vi} from "vitest";
import {createServer, type ViteDevServer} from "vite";

import {ApiClient, EventStream} from "../src/api";
import {AppStore} from "../src/store";

let server: ViteDevServer;
let base: string;
beforeAll(async () => {
  server = await createServer({mode: "demo", logLevel: "silent",
    optimizeDeps: {noDiscovery: true, include: []},
    server: {host: "127.0.0.1", port: 0, hmr: false, watch: null}});
  await server.listen();
  base = server.resolvedUrls!.local[0] + "api/v1";
});
afterAll(async () => { await server?.close(); });

async function read(path: string) {
  const response = await fetch(base + path);
  expect(response.headers.get("content-type")).toContain("application/json");
  expect(response.ok).toBe(true);
  return response.json();
}

it("serves fixed and explicitly marked example data for every read page", async () => {
  const paths = ["/auth/status", "/state", "/device", "/sensors", "/telemetry", "/media", "/profiles", "/diagnostics"];
  const first = await Promise.all(paths.map(read));
  expect(first).toEqual(await Promise.all(paths.map(read)));
  for (const body of first) expect(body.demo).toBe(true);
  const [auth, {state}, device, {sensors}, telemetry, media, {profiles}, diagnostics] = first;
  expect(auth).toMatchObject({required: false, authenticated: true});
  expect(device.connected).toBe(true);
  expect(state.slots).toHaveLength(6);
  expect(sensors.map((sensor: {measurementId: string}) => sensor.measurementId)).toContain("gpu.temperature");
  expect(telemetry.measurements["gpu.vram.used"].value).toBe(8.5 * 1024 ** 3);
  expect(media.factory).toContain("Ryuo_IV_MIKU_WW_01.mp4");
  expect(media.custom).toContain("aurora.mp4");
  expect(media.adb.available).toBe(false);
  expect(profiles).toContainEqual(expect.objectContaining({slug: state.active_profile, factory: false}));
  expect(profiles.filter((p: {factory: boolean}) => p.factory)).toHaveLength(5);
  expect(diagnostics.security.bindMode).toBe("loopback");
});

it("emits the same marked snapshot over the event stream as the read endpoints", async () => {
  const abort = new AbortController();
  try {
    const response = await fetch(base + "/events", {signal: abort.signal});
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let event = "";
    while (!event.includes("\n\n")) {
      const chunk = await reader.read();
      if (chunk.done) break;
      event += decoder.decode(chunk.value, {stream: true});
    }
    expect(event).toContain("id: 1\n");
    const snapshot = JSON.parse(event.split("\n").find(line => line.startsWith("data: "))!.slice(6));
    expect(snapshot.demo).toBe(true);
    expect(snapshot.state).toEqual((await read("/state")).state);
    expect(snapshot.telemetry.measurements).toEqual((await read("/telemetry")).measurements);
    expect(snapshot.device.model).toBe((await read("/device")).model);
  } finally { abort.abort(); }
});

it("handles writes and unknown API calls inside the demo and preserves its fixtures", async () => {
  const mutation = await fetch(base + "/brightness", {method: "PATCH", body: '{"brightness":1}'});
  expect(mutation.status).toBe(405);
  expect(await mutation.json()).toMatchObject({demo: true, error: "demo_read_only"});
  const unknown = await fetch(base + "/not-a-demo-resource");
  expect(unknown.status).toBe(404);
  expect(await unknown.json()).toMatchObject({demo: true});
  expect((await read("/state")).state.brightness).toBe(85);
});

it("exports factory and custom downloads with only importable profile fields", async () => {
  const keys = [
    "slug", "name", "factory", "schema_version", "screen_mode", "media", "playback_modes",
    "slots", "brightness", "temperature_unit", "refresh_interval", "title_colors",
    "content_colors", "opacity", "rgb_mode", "rgb_target", "thermal_source", "sensor_selectors",
  ].sort();
  const catalog = await read("/profiles");
  for (const slug of ["miku-single-01", "aurora-split"]) {
    const profile = await read(`/profiles/${slug}/export`);
    expect(Object.keys(profile).sort()).toEqual(keys);
    expect(profile).toEqual(catalog.profiles.find((item: {slug: string}) => item.slug === slug));
  }
});

it("recovers the connected store after interrupting a real demo event stream", async () => {
  const disconnect = new AbortController();
  const realFetch = globalThis.fetch;
  let retry: (() => void) | undefined;
  let firstStream = true;
  vi.stubGlobal("fetch", (input: string, init: RequestInit = {}) => {
    const url = new URL(input, base);
    if (url.pathname.endsWith("/events") && firstStream) {
      firstStream = false;
      init = {...init, signal: AbortSignal.any([init.signal!, disconnect.signal])};
    }
    return realFetch(url, init);
  });
  const store = new AppStore(new ApiClient(), new EventStream(), run => { retry = run; });
  try {
    await store.start();
    await vi.waitFor(() => expect(store.value.lastEventId).toBe(1));
    const first = store.value.snapshot;
    disconnect.abort(new Error("test stream interrupted"));
    await vi.waitFor(() => expect(store.value.connected).toBe(false));
    expect(store.value.error).toBeTruthy();
    retry!();
    await vi.waitFor(() => expect(store.value.lastEventId).toBe(2));
    expect(store.value).toMatchObject({connected: true, error: null, snapshot: first});
  } finally {
    store.stop();
    vi.unstubAllGlobals();
  }
});
