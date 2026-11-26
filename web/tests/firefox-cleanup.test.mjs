// @vitest-environment node
import {spawn} from "node:child_process";
import {EventEmitter, once} from "node:events";
import {existsSync} from "node:fs";
import {mkdtemp, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {expect, it, vi} from "vitest";
import {stopFirefox} from "../demo/firefox-cleanup.mjs";

it("force-kills only the captured child and waits for exit before removing its profile", async () => {
  const profile = await mkdtemp(join(tmpdir(), "ryuo-cleanup-test-"));
  const child = Object.assign(new EventEmitter(), {
    pid: 1234, exitCode: null, signalCode: null, kill: vi.fn(() => true),
  });
  const closed = new Promise(resolve => child.once("close", resolve));
  vi.useFakeTimers();
  const cleanup = stopFirefox(child, closed, profile);
  try {
    expect(child.kill.mock.calls).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(child.kill.mock.calls).toEqual([["SIGTERM"], ["SIGKILL"]]);
    expect(existsSync(profile)).toBe(true);
    child.signalCode = "SIGKILL";
    child.emit("exit", null, "SIGKILL");
    child.emit("close", null, "SIGKILL");
    await cleanup;
    expect(existsSync(profile)).toBe(false);
  } finally {
    child.emit("exit", 0);
    child.emit("close", 0);
    vi.useRealTimers();
    await cleanup;
    await rm(profile, {recursive: true, force: true});
  }
});

it("settles with an error and retains the profile when forced exit cannot be confirmed", async () => {
  const profile = await mkdtemp(join(tmpdir(), "ryuo-cleanup-test-"));
  const child = Object.assign(new EventEmitter(), {
    pid: 1234, exitCode: null, signalCode: null, kill: vi.fn(), unref: vi.fn(),
  });
  vi.useFakeTimers();
  try {
    const cleanup = stopFirefox(child, new Promise(() => {}), profile);
    const settled = expect(cleanup).rejects.toThrow(profile);
    await vi.advanceTimersByTimeAsync(10_000);
    await settled;
    expect(existsSync(profile)).toBe(true);
  } finally {
    vi.useRealTimers();
    await rm(profile, {recursive: true, force: true});
  }
});

it("releases inherited stderr after the captured parent has exited", async () => {
  const profile = await mkdtemp(join(tmpdir(), "ryuo-cleanup-test-"));
  // The descendant keeps the parent's stderr pipe open until its reader goes away.
  const writer = `
    process.stderr.on("error", () => process.exit(0));
    setInterval(() => process.stderr.write("."), 20);
    setTimeout(() => process.exit(1), 10000).unref();
  `;
  const launcher = `
    require("node:child_process").spawn(process.execPath, ["-e", process.argv[1]],
      {stdio: ["ignore", "ignore", "inherit"]}).unref();
  `;
  const child = spawn(process.execPath, ["-e", launcher, writer], {stdio: ["ignore", "ignore", "pipe"]});
  const closed = once(child, "close");
  try {
    const [exit] = await Promise.all([once(child, "exit"), once(child.stderr, "data")]);
    expect(exit).toEqual([0, null]);
    expect(child.stderr.destroyed).toBe(false);
    await stopFirefox(child, closed, profile);
    expect(child.stderr.destroyed, "cleanup returned with a live inherited stderr pipe").toBe(true);
    await closed;
    expect(existsSync(profile)).toBe(false);
  } finally {
    child.stderr.destroy();
    await closed;
    await rm(profile, {recursive: true, force: true});
  }
});

it("finishes a graceful exit independently of stdio close and releases each owned pipe", async () => {
  const profile = await mkdtemp(join(tmpdir(), "ryuo-cleanup-test-"));
  const child = Object.assign(new EventEmitter(), {
    pid: 1234, exitCode: null, signalCode: null, kill: vi.fn(),
    stdin: {destroy: vi.fn()}, stdout: {destroy: vi.fn()}, stderr: {destroy: vi.fn()},
  });
  const closed = new Promise(resolve => child.once("close", resolve));
  vi.useFakeTimers();
  const cleanup = stopFirefox(child, closed, profile);
  try {
    child.signalCode = "SIGTERM";
    child.emit("exit", null, "SIGTERM");
    expect(child.stderr.destroy).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);
    for (const pipe of [child.stdin, child.stdout, child.stderr]) expect(pipe.destroy).toHaveBeenCalledOnce();
    await cleanup;
    expect(child.kill.mock.calls).toEqual([["SIGTERM"]]);
    expect(existsSync(profile)).toBe(false);
  } finally {
    child.emit("close", null, "SIGTERM");
    await vi.advanceTimersByTimeAsync(10_000);
    vi.useRealTimers();
    await cleanup;
    await rm(profile, {recursive: true, force: true});
  }
});
