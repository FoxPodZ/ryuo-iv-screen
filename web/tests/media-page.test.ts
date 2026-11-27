import {expect, it, vi} from "vitest";
import {MediaPage} from "../src/ui/media-page";
import {change, click, filename, get, json, mutation, render, setup} from "./library-fixture";

it("uses exact API classifications and server preview paths, with delete reserved for custom files", async () => {
  const {store, requests} = await setup((path, init) =>
    init.method === "DELETE" && path.endsWith("/user-one.mp4")
      ? json({jobId: "done", name: "user-one.mp4", confirmed: true, applied: true, error: null}) : undefined);
  const root = await render(new MediaPage(), store);
  const factory = get(root, '[aria-label="Заводские файлы"]');
  const custom = get(root, '[aria-label="Пользовательские файлы"]');
  await vi.waitFor(() => expect(factory.textContent).toContain(filename));
  expect(factory.querySelector('[data-delete]')).toBeNull();
  click(factory, "[data-preview]");
  await vi.waitFor(() => expect(get<HTMLVideoElement>(root, "video").getAttribute("src"))
    .toBe(`/api/v1/media/preview/proxy/${filename}`));
  click(custom, "[data-delete]");
  await vi.waitFor(() => expect(get(root, '[role="alertdialog"]').textContent).toContain("user-one.mp4"));
  expect(requests.some(({init}) => init.method === "DELETE")).toBe(false);
  click(root, "[data-confirm-delete]");
  await vi.waitFor(() => expect(requests.some(({path, init}) => path.endsWith("/user-one.mp4") &&
    init.method === "DELETE")).toBe(true));
});

it("saves playback mode and keyboard ordering independently for the two zones", async () => {
  const {store, requests} = await setup((path) => path.endsWith("/screen") ? json(mutation) : undefined);
  const root = await render(new MediaPage(), store);
  change(root, '[name="playback-mode-1"]', "Random");
  click(root, '[data-zone="2"] [data-move-down]');
  await vi.waitFor(() => expect(get<HTMLButtonElement>(root, "[data-save-playlists]").disabled).toBe(false));
  click(root, "[data-save-playlists]");
  await vi.waitFor(() => expect(requests.find(({path}) => path.endsWith("/screen"))).toBeDefined());
  const {init} = requests.find(({path}) => path.endsWith("/screen"))!;
  expect((init.headers as Headers).get("If-Match")).toBe("4");
  expect(JSON.parse(String(init.body))).toMatchObject({
    playback_modes: ["Random", "Single"], media: [[filename, "user-one.mp4"], [filename, "user-one.mp4"]],
  });
});

it("keeps the existing catalog visible with ADB and FFmpeg unavailable", async () => {
  const {store} = await setup(undefined, false);
  const root = await render(new MediaPage(), store);
  await vi.waitFor(() => expect(root.textContent).toContain("ADB недоступен"));
  expect(root.textContent).toContain("FFmpeg недоступен");
  expect(root.textContent).toContain(filename);
  expect(get<HTMLButtonElement>(root, "[data-preview]").disabled).toBe(true);
  const upload = get(root, "upload-zone");
  expect(get<HTMLInputElement>(upload.shadowRoot!, 'input[type="file"]').disabled).toBe(true);
});

it("opens each new page from the app shell with one main landmark", async () => {
  const {RyuoApp} = await import("../src/ui/ryuo-app");
  const {store} = await setup();
  const app = new RyuoApp();
  app.store = store;
  document.body.append(app);
  await app.updateComplete;
  const root = app.shadowRoot!;
  const nav = get(root, "nav");
  await vi.waitFor(() => expect(get(root, "dashboard-page").shadowRoot?.querySelector("h1")).toBeTruthy());
  expect(root.querySelectorAll("main")).toHaveLength(1);
  expect(get(root, "dashboard-page").shadowRoot?.querySelector("main")).toBeNull();
  for (const [label, selector] of [
    ["Медиатека", "media-page"], ["Профили", "profiles-page"], ["Настройки", "settings-page"],
  ]) {
    const tab = Array.from(nav.querySelectorAll("button")).find((button) => button.textContent?.trim() === label)!;
    tab.click();
    await vi.waitFor(() => expect(root.querySelector(selector)).toBeTruthy());
    expect(tab.getAttribute("aria-current")).toBe("page");
    expect(root.querySelectorAll("main")).toHaveLength(1);
  }
});

it.each([true, false])("identifies the selected transfer device with ADB availability %s", async available => {
  const {store} = await setup(undefined, available);
  const root = await render(new MediaPage(), store);
  await vi.waitFor(() => expect(root.textContent).toContain("adb-sensitive-serial"));
});

it("selects Single when the last media item is removed", async () => {
  const {store} = await setup();
  const root = await render(new MediaPage(), store);
  change(root, '[name="playback-mode-1"]', "Random");
  for (let index = 0; index < 2; index++) {
    click(root, '[data-zone="1"] button[aria-label^="Убрать"]');
    await vi.waitFor(() => expect(root.querySelectorAll('[data-zone="1"] ol li')).toHaveLength(1-index));
  }
  expect(get<HTMLSelectElement>(root, '[name="playback-mode-1"]').value).toBe("Single");
});
