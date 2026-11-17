import {expect, it, vi} from "vitest";
import {SettingsPage} from "../src/ui/settings-page";
import {change, click, get, json, mutation, render, setup} from "./library-fixture";

it("shows the current source and applies stable manual selectors, interval and unit with a revision", async () => {
  const {store, requests} = await setup((path) => path.endsWith("/telemetry-settings") ? json(mutation) : undefined);
  const root = await render(new SettingsPage(), store);
  await vi.waitFor(() => expect(get<HTMLSelectElement>(root, '[name="gpu"]').options.length).toBeGreaterThan(1));
  expect(root.textContent).toContain("gpu_busy_percent");
  expect(root.textContent).toContain("amd");
  for (const name of ["gpu", "motherboard"]) {
    const option = get<HTMLSelectElement>(root, `[name="${name}"]`).options[1];
    change(root, `[name="${name}"]`, option.value);
  }
  change(root, '[name="refresh_interval"]', "2", "input");
  change(root, '[name="temperature_unit"]', "Fahrenheit");
  await vi.waitFor(() => expect(get<HTMLButtonElement>(root, "[data-save-settings]").disabled).toBe(false));
  click(root, "[data-save-settings]");
  await vi.waitFor(() => expect(requests.find(({path}) => path.endsWith("/telemetry-settings"))).toBeDefined());
  const patch = requests.find(({path}) => path.endsWith("/telemetry-settings"))!;
  expect(JSON.parse(String(patch.init.body))).toEqual({
    revision: 4, refresh_interval: 2, temperature_unit: "Fahrenheit",
    sensor_selectors: {
      gpu: {provider: "amd", device: "0000:08:00.0", channel: "gpu.load"},
      motherboard: {provider: "hwmon", device: "platform/nct6775.656/nct6799", channel: "temp2"},
    },
  });
});

it("copies allowlisted diagnostics and explains where listen and password changes take effect", async () => {
  const clipboard = vi.fn(async (_value: string) => {});
  Object.defineProperty(navigator, "clipboard", {configurable: true, value: {writeText: clipboard}});
  const {store, requests} = await setup(undefined, false);
  const root = await render(new SettingsPage(), store);
  await vi.waitFor(() => expect(root.textContent).toContain("LAN"));
  expect(root.textContent).toContain("ADB недоступен");
  expect(root.textContent).toContain("FFmpeg недоступен");
  expect(root.textContent).toMatch(/сесси/i);
  expect(root.textContent).toContain("config.toml");
  expect(root.textContent).toMatch(/перезапуск/i);
  expect(root.querySelector('input[type="password"]')).toBeNull();
  click(root, "[data-copy-diagnostics]");
  await vi.waitFor(() => expect(clipboard).toHaveBeenCalledTimes(1));
  const copied = clipboard.mock.calls[0][0];
  expect(JSON.parse(copied)).toMatchObject({security: {bindMode: "lan"}, media: {adb: false, ffmpeg: false}});
  expect(copied).not.toMatch(/secret|serial|csrf|token|verifier/i);
  expect(requests.every(({init}) => !init.method || init.method === "GET")).toBe(true);
});
