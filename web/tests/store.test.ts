import {describe, expect, it, vi} from "vitest";

import type {AuthStatus, MutationResult, SensorsResponse, SnapshotDocument} from "../src/api-types";
import {ApiError, EventStream, type ScreenPatchKind} from "../src/api";
import {AppStore, type ApiGateway, type EventConnection, type EventConnector} from "../src/store";

const snapshot = (revision: number, brightness = 85): SnapshotDocument => ({
  revision,
  state: {
    schema_version: 1,
    revision,
    active_profile: "Miku Cycle",
    screen_mode: "Full Screen",
    media: [["Ryuo_IV_MIKU_WW_01.mp4"]],
    playback_modes: ["Cycle"],
    slots: Array.from({length: 6}, () => ({enabled: false, measurement_id: "", widget: "", label: null})),
    brightness,
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
  device: {connected: true, phase: "healthy", health: "healthy", model: "Ryuo IV", firmware: "1.2.3", uptime: 42},
  telemetry: {sampledAt: 12, measurements: {}, errors: {}},
});

class FakeApi implements ApiGateway {
  auth: AuthStatus = {required: false, authenticated: true, csrfToken: null};
  current = snapshot(1);
  loginCalls: string[] = [];
  patchCalls: Array<{kind: ScreenPatchKind; revision: number; changes: Record<string, unknown>}> = [];
  patchError: ApiError | null = null;
  mutationResult: MutationResult | null = null;

  async authStatus(): Promise<AuthStatus> { return this.auth; }
  async loadSnapshot(): Promise<SnapshotDocument> { return this.current; }
  async login(password: string): Promise<AuthStatus> {
    this.loginCalls.push(password);
    if (password === "bad") throw new ApiError(401, "invalid_credentials", "Неверный пароль");
    this.auth = {required: true, authenticated: true, csrfToken: "csrf", expiresIn: 10};
    return this.auth;
  }
  async loadSensors(): Promise<SensorsResponse> {
    return {sensors: [], error: null};
  }
  async patchState(kind: ScreenPatchKind, revision: number, changes: Record<string, unknown>): Promise<MutationResult> {
    this.patchCalls.push({kind, revision, changes});
    if (this.patchError) throw this.patchError;
    this.current = snapshot(revision + 1, typeof changes.brightness === "number" ? changes.brightness : this.current.state.brightness);
    return this.mutationResult ?? {revision: revision + 1, saved: true, queued: true, applied: false, acked: false, error: null};
  }
}

class ManualConnector implements EventConnector {
  starts: Array<number | null> = [];
  onEvent?: (id: number, value: SnapshotDocument) => void;
  onError?: (error: unknown) => void;

  connect(lastEventId: number | null, onEvent: (id: number, value: SnapshotDocument) => void, onError: (error: unknown) => void): EventConnection {
    this.starts.push(lastEventId);
    this.onEvent = onEvent;
    this.onError = onError;
    return {close: vi.fn()};
  }
}

describe("AppStore", () => {
  it("sends Last-Event-ID and decodes an SSE snapshot", async () => {
    const body = `id: 9\nevent: snapshot\ndata: ${JSON.stringify(snapshot(3))}\n\n`;
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: {"Content-Type": "text/event-stream"},
    }));
    vi.stubGlobal("fetch", fetchMock);
    const received = new Promise<{id: number; value: SnapshotDocument}>((resolve) => {
      new EventStream().connect(7, (id, value) => resolve({id, value}), () => undefined);
    });
    await expect(received).resolves.toMatchObject({id: 9, value: {revision: 3}});
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Last-Event-ID")).toBe("7");
  });

  it("loads once, merges monotonic SSE snapshots and preserves last good data on errors", async () => {
    const api = new FakeApi();
    const stream = new ManualConnector();
    const scheduled: Array<{delay: number; run: () => void}> = [];
    const store = new AppStore(api, stream, (run, delay) => {
      scheduled.push({delay, run});
      return 1;
    });

    expect(store.value.phase).toBe("loading");
    await store.start();
    expect(store.value.snapshot?.revision).toBe(1);
    expect(Object.isFrozen(store.value.snapshot)).toBe(true);
    expect(Object.isFrozen(store.value.snapshot?.state)).toBe(true);
    expect(stream.starts).toEqual([null]);

    stream.onEvent?.(7, snapshot(2, 40));
    stream.onEvent?.(6, snapshot(99, 99));
    expect(store.value.snapshot?.state.brightness).toBe(40);
    expect(store.value.lastEventId).toBe(7);

    stream.onError?.(new Error("Соединение SSE потеряно"));
    expect(store.value.snapshot?.revision).toBe(2);
    expect(store.value.error).toContain("SSE");
    expect(scheduled[0].delay).toBe(500);
    scheduled[0].run();
    expect(stream.starts).toEqual([null, 7]);

    stream.onError?.(new Error("again"));
    expect(scheduled[1].delay).toBe(1000);
  });

  it("bounds exponential retry and keeps last data while reconnecting", async () => {
    const api = new FakeApi();
    const stream = new ManualConnector();
    const delays: number[] = [];
    let reconnect: (() => void) | undefined;
    const store = new AppStore(api, stream, (run, delay) => {
      delays.push(delay);
      reconnect = run;
      return delays.length;
    });
    await store.start();
    for (let index = 0; index < 8; index += 1) {
      stream.onError?.(new Error("offline"));
      reconnect?.();
    }
    expect(Math.max(...delays)).toBe(10_000);
    expect(store.value.snapshot?.revision).toBe(1);
  });

  it("enters login on LAN 401, never retains password, and reconnects after login", async () => {
    const api = new FakeApi();
    api.auth = {required: true, authenticated: false, csrfToken: null};
    const stream = new ManualConnector();
    const store = new AppStore(api, stream);
    await store.start();
    expect(store.value.phase).toBe("login");
    expect(stream.starts).toEqual([]);

    await store.login("secret-password");
    expect(store.value.phase).toBe("ready");
    expect(store.value.csrfToken).toBe("csrf");
    expect(JSON.stringify(store.value)).not.toContain("secret-password");
    expect(stream.starts).toEqual([null]);

    stream.onError?.(new ApiError(401, "authentication_required", "Сессия истекла"));
    expect(store.value.phase).toBe("login");
    expect(store.value.snapshot?.revision).toBe(1);
    expect(store.value.error).toContain("Сессия");
  });

  it("keeps login actionable after invalid credentials", async () => {
    const api = new FakeApi();
    api.auth = {required: true, authenticated: false, csrfToken: null};
    const store = new AppStore(api, new ManualConnector());
    await store.start();
    await store.login("bad");
    expect(store.value.phase).toBe("login");
    expect(store.value.error).toBe("Неверный пароль");
    expect(JSON.stringify(store.value)).not.toContain('"bad"');
  });

  it("expires a LAN session on schedule even while SSE remains healthy", async () => {
    const api = new FakeApi();
    api.auth = {required: true, authenticated: true, csrfToken: "csrf", expiresIn: 2};
    const stream = new ManualConnector();
    const scheduled: Array<{delay: number; run: () => void; cancelled: boolean}> = [];
    const store = new AppStore(
      api,
      stream,
      (run, delay) => {
        const entry = {delay, run, cancelled: false};
        scheduled.push(entry);
        return entry;
      },
      (handle) => { (handle as {cancelled: boolean}).cancelled = true; },
    );
    await store.start();
    expect(store.value.phase).toBe("ready");
    expect(scheduled[0].delay).toBe(2000);

    scheduled[0].run();
    expect(store.value.phase).toBe("login");
    expect(store.value.csrfToken).toBeNull();
    expect(store.value.snapshot?.revision).toBe(1);
    expect(store.value.error).toContain("истекла");
  });

  it("invalidates old expiry timers on relogin, stop and local mode", async () => {
    const api = new FakeApi();
    api.auth = {required: true, authenticated: true, csrfToken: "old", expiresIn: 1};
    const stream = new ManualConnector();
    const scheduled: Array<{delay: number; run: () => void; cancelled: boolean}> = [];
    const store = new AppStore(
      api,
      stream,
      (run, delay) => {
        const entry = {delay, run, cancelled: false};
        scheduled.push(entry);
        return entry;
      },
      (handle) => { (handle as {cancelled: boolean}).cancelled = true; },
    );
    await store.start();
    const old = scheduled[0];
    await store.login("new-secret");
    expect(old.cancelled).toBe(true);
    old.run();
    expect(store.value.phase).toBe("ready");

    const current = scheduled[1];
    store.stop();
    expect(current.cancelled).toBe(true);
    current.run();
    expect(store.value.phase).toBe("ready");

    const localApi = new FakeApi();
    const localScheduled = vi.fn();
    const localStore = new AppStore(localApi, new ManualConnector(), localScheduled);
    await localStore.start();
    expect(localScheduled).not.toHaveBeenCalled();
  });

  it("patches the current revision and refreshes on success or conflict without overwriting", async () => {
    const api = new FakeApi();
    const store = new AppStore(api, new ManualConnector());
    await store.start();
    await store.patchScreen("brightness", {brightness: 44});
    expect(api.patchCalls[0]).toEqual({kind: "brightness", revision: 1, changes: {brightness: 44}});
    expect(store.value.snapshot?.revision).toBe(2);
    expect(store.value.snapshot?.state.brightness).toBe(44);

    api.current = snapshot(3, 77);
    api.patchError = new ApiError(409, "revision_conflict", "stale");
    const outcome = await store.patchScreen("screen", {opacity: 50});
    expect(outcome).toMatchObject({ok: false, conflict: true});
    expect(store.value.snapshot?.revision).toBe(3);
    expect(store.value.snapshot?.state.brightness).toBe(77);
    expect(store.value.mutationError).toContain("Конфликт ревизий");
  });

  it("returns a failed mutation outcome when the device did not queue saved state", async () => {
    const api = new FakeApi();
    api.mutationResult = {
      revision: 2, saved: true, queued: false, applied: false,
      acked: false, error: "device queue is full",
    };
    const store = new AppStore(api, new ManualConnector());
    await store.start();

    const outcome = await store.patchScreen("brightness", {brightness: 44});

    expect(outcome.ok).toBe(false);
    expect(outcome.error).toContain("device queue is full");
    expect(store.value.mutationError).toContain("device queue is full");
  });
});

it("drops a previous daemon cursor and accepts the restarted snapshot", async () => {
  const api = new FakeApi();
  const events = new ManualConnector();
  const retry: Array<() => void> = [];
  const store = new AppStore(api, events, (fn) => { retry.push(fn); return 0; });
  await store.start();
  events.onEvent!(90000, snapshot(12));
  events.onError!(new ApiError(409, "stream_reset", "Stream restarted"));
  retry.pop()!();
  expect(events.starts.at(-1)).toBe(null);
  events.onEvent!(1, snapshot(1));
  expect(store.value.snapshot?.revision).toBe(1);
  expect(store.value.lastEventId).toBe(1);
  store.stop();
});
