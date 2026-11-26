// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {once} from "node:events";
import {mkdir, mkdtemp, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join, resolve} from "node:path";
import {createInterface} from "node:readline";
import {setTimeout as delay} from "node:timers/promises";
import {fileURLToPath} from "node:url";

import {stopFirefox} from "./firefox-cleanup.mjs";

const origin = "http://127.0.0.1:5173";
const desktop = fileURLToPath(new URL("../../docs/images/", import.meta.url));
const mobile = process.argv[2];
const status = await fetch(origin + "/api/v1/auth/status");
assert.equal((await status.json()).demo, true, "Start npm run demo before capturing");
const profile = await mkdtemp(join(tmpdir(), "ryuo-demo-firefox-"));
const firefox = spawn(process.env.FIREFOX || "firefox", ["--headless", "--no-remote",
  "--profile", profile, "--remote-debugging-port", "0", "about:blank"],
  {stdio: ["ignore", "ignore", "pipe"]});
const closed = new Promise(resolve => firefox.once("close", resolve));
firefox.on("error", error => console.error("Firefox:", error.message));
let socket;
try {
  const lines = createInterface({input: firefox.stderr, signal: AbortSignal.timeout(15_000)});
  let endpoint;
  for await (const line of lines) {
    endpoint = /WebDriver BiDi listening on (ws:\/\/127\.0\.0\.1:\d+)/.exec(line)?.[1];
    if (endpoint) break;
  }
  firefox.stderr.resume();
  assert.ok(endpoint, "Headless Firefox did not start its WebDriver BiDi endpoint");
  socket = new WebSocket(endpoint + "/session");
  await once(socket, "open", {signal: AbortSignal.timeout(5_000)});

  let sequence = 0;
  async function command(method, params) {
    const id = ++sequence;
    const reply = once(socket, "message", {signal: AbortSignal.timeout(15_000)});
    socket.send(JSON.stringify({id, method, params}));
    const [event] = await reply;
    const message = JSON.parse(event.data);
    assert.equal(message.id, id);
    assert.equal(message.type, "success", message.message);
    return message.result;
  }

  const session = await command("session.new", {capabilities: {}});
  console.log("Firefox", session.capabilities.browserVersion);
  const {contexts} = await command("browsingContext.getTree", {});
  const context = contexts[0].context;
  const viewport = (width, height) => command("browsingContext.setViewport",
    {context, viewport: {width, height}, devicePixelRatio: 1});
  async function evaluate(expression) {
    const result = await command("script.evaluate", {expression, target: {context}, awaitPromise: true});
    assert.equal(result.type, "success", result.exceptionDetails?.text);
    return result.result.value;
  }
  const app = 'document.querySelector("ryuo-app")?.shadowRoot';
  async function waitFor(expression) {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate(`Boolean(${expression})`)) return;
      await delay(50);
    }
    throw new Error("Page did not become ready: " + expression);
  }
  async function capture(tab, component, selector, text, path) {
    await evaluate(`[...${app}.querySelectorAll("nav button")].find(b => b.textContent.trim() === ${JSON.stringify(tab)}).click()`);
    const page = `${app}.querySelector("${component}")?.shadowRoot`;
    await waitFor(`${page}?.querySelector(${JSON.stringify(selector)})?.textContent.includes(${JSON.stringify(text)})`);
    await waitFor(`${app}.querySelector(".stream")?.textContent.trim() === "Демонстрационные данные"`);
    await evaluate("document.fonts.ready.then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))");
    assert.ok(await evaluate("document.documentElement.scrollWidth <= innerWidth"), "Page overflows horizontally: " + tab);
    if (component === "screen-page") {
      await waitFor(`[...${page}.querySelectorAll("sensor-slot")].filter(slot =>
        slot.shadowRoot?.querySelector("select")?.value).length === 6`);
      const fits = await evaluate(`[...${page}.querySelectorAll(".controls input")].every(input =>
        input.getBoundingClientRect().right <= input.closest("label").getBoundingClientRect().right + 1)`);
      assert.ok(fits, "Screen controls extend beyond their own columns");
    }
    assert.ok(await evaluate(`performance.getEntriesByType("resource").every(r => new URL(r.name).origin === location.origin)`),
      "Demo page requested a resource outside its local server");
    const {data} = await command("browsingContext.captureScreenshot", {context, origin: "viewport"});
    await writeFile(path, Buffer.from(data, "base64"));
    console.log(tab, path);
  }

  await viewport(1440, 1100);
  await command("browsingContext.navigate", {context, url: origin, wait: "complete"});
  await waitFor(`${app}?.querySelector("nav button")`);
  assert.ok(await evaluate(`(() => {
    const credit = document.querySelector('footer a[href="https://github.com/foxpodz/ryuo-iv-screen"]');
    return credit?.checkVisibility() && credit.textContent === "FoxPodZ (foxpodz.de)";
  })()`), "Visible original project credit is missing");
  await mkdir(desktop, {recursive: true});
  await capture("Dashboard", "dashboard-page", ".grid", "8.5 GiB", join(desktop, "dashboard.png"));
  await capture("Экран", "screen-page", ".preview", "не снимок экрана", join(desktop, "screen-editor.png"));
  await capture("Медиатека", "media-page", ".columns", "aurora.mp4", join(desktop, "media-library.png"));
  await capture("Профили", "profiles-page", ".list", "Miku Single 01", join(desktop, "profiles.png"));
  if (mobile) {
    await viewport(390, 844);
    await capture("Dashboard", "dashboard-page", ".grid", "8.5 GiB", resolve(mobile));
  }
} finally {
  socket?.close();
  await stopFirefox(firefox, closed, profile);
}
