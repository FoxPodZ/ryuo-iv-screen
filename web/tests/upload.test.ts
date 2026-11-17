import {expect, it, vi} from "vitest";
import {UploadZone} from "../src/ui/upload-zone";
import {click, get, render, setup} from "./library-fixture";

class Transfer extends EventTarget {
  static current: Transfer;
  upload = new EventTarget();
  headers = new Headers();
  body?: File;
  status = 0;
  responseText = "";
  constructor() {super(); Transfer.current = this;}
  open(_method: string, _path: string) {}
  setRequestHeader(name: string, value: string) {this.headers.set(name, value);}
  send(body: File) {this.body = body;}
  abort() {this.dispatchEvent(new Event("abort"));}
  finish(confirmed: boolean, status: number) {
    this.status = status;
    this.responseText = JSON.stringify({name: "user-assigned.mp4", confirmed, error: confirmed ? null : "No confirmation"});
    this.dispatchEvent(new Event("load"));
  }
}

async function fixture() {
  const {store} = await setup();
  await store.loadMedia();
  vi.stubGlobal("XMLHttpRequest", Transfer);
  const zone = new UploadZone();
  zone.disabled = false;
  const root = await render(zone, store);
  const choose = (file: File) => {
    const input = get<HTMLInputElement>(root, 'input[type="file"]');
    Object.defineProperty(input, "files", {configurable: true, value: [file]});
    input.dispatchEvent(new Event("change"));
  };
  return {zone, root, choose};
}

it("rejects unsupported files", async () => {
  const {root, choose} = await fixture();
  choose(new File(["text"], "readme.txt"));
  await vi.waitFor(() => expect(get(root, '[role="alert"]').textContent).toMatch(/MP4.*GIF.*PNG.*JPG/));
});

it("sends the raw file with safe metadata and confirms success only after the server responds", async () => {
  const {root, choose} = await fixture();
  const file = new File(["bytes"], "日本語.mp4");
  choose(file);
  expect(Transfer.current.body).toBe(file);
  expect(Transfer.current.headers.get("Content-Type")).toBe("application/octet-stream");
  expect(Transfer.current.headers.get("X-Filename")).toMatch(/^[A-Za-z0-9_.-]+$/);
  expect(Transfer.current.headers.get("X-CSRF-Token")).toBe("secret");
  Transfer.current.upload.dispatchEvent(new ProgressEvent("progress", {lengthComputable: true, loaded: 2, total: 5}));
  await vi.waitFor(() => expect(get<HTMLProgressElement>(root, "progress").value).toBe(40));
  Transfer.current.upload.dispatchEvent(new Event("load"));
  await vi.waitFor(() => expect(root.textContent).toMatch(/обрабатывает/i));
  expect(root.querySelector("[data-cancel-upload]")).toBeNull();
  expect(root.textContent).not.toContain("user-assigned.mp4");
  Transfer.current.finish(true, 201);
  await vi.waitFor(() => expect(root.textContent).toContain("user-assigned.mp4"));
});

it("allows cancellation only while sending and surfaces an unconfirmed response as failure", async () => {
  const {root, choose} = await fixture();
  choose(new File(["bytes"], "sample.gif"));
  await vi.waitFor(() => expect(root.querySelector("[data-cancel-upload]")).toBeTruthy());
  click(root, "[data-cancel-upload]");
  await vi.waitFor(() => expect(root.textContent).toMatch(/отменена/i));
  choose(new File(["bytes"], "sample.png"));
  Transfer.current.upload.dispatchEvent(new Event("load"));
  Transfer.current.finish(false, 201);
  await vi.waitFor(() => expect(get(root, '[role="alert"]').textContent).toContain("No confirmation"));
  expect(root.textContent).not.toContain("user-assigned.mp4");
});

it("accepts a second upload after confirmation even while the catalog refresh is pending", async () => {
  let refresh: () => void = () => undefined;
  const {root, choose} = await fixture();
  const nextFetch = globalThis.fetch;
  vi.stubGlobal("fetch", (path: string, init: RequestInit) => path.endsWith("/media")
    ? new Promise<Response>((resolve) => {
      refresh = () => {void nextFetch(path, init).then(resolve);};
    })
    : nextFetch(path, init));
  try {
    choose(new File(["first"], "first.mp4"));
    const first = Transfer.current;
    first.upload.dispatchEvent(new Event("load"));
    first.finish(true, 201);
    await vi.waitFor(() => expect(root.textContent).toContain("user-assigned.mp4"));
    const second = new File(["second"], "second.mp4");
    choose(second);
    expect(Transfer.current.body).toBe(second);
    expect(Transfer.current).not.toBe(first);
  } finally {
    refresh();
  }
});
