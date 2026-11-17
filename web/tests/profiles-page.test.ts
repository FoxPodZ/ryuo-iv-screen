import {expect, it, vi} from "vitest";
import {ProfilesPage} from "../src/ui/profiles-page";
import {change, click, get, json, mutation, profiles, render, setup} from "./library-fixture";

it("renders five built-in Miku examples and the active indicator", async () => {
  const {store} = await setup();
  const root = await render(new ProfilesPage(), store);
  await vi.waitFor(() => expect(root.textContent).toContain("Miku Cycle"));
  for (const n of [1, 2, 3, 4]) expect(root.textContent).toContain(`Miku Single 0${n}`);
  expect(get(root, '[data-profile="miku-cycle"] [aria-current="true"]').textContent).toContain("Активный");
  expect(get(root, '[data-profile="miku-cycle"]').querySelector("[data-delete]")).toBeNull();
});

it("creates from screen state, duplicates built-ins and renames by server slug", async () => {
  const {store, requests} = await setup((path, init) => {
    if ((init.method === "POST" && (path.endsWith("/duplicate") || path.endsWith("/profiles"))) ||
        (init.method === "PATCH" && path.endsWith("/custom"))) return json({profile: profiles[5]}, 201);
  });
  const root = await render(new ProfilesPage(), store);
  await vi.waitFor(() => expect(root.textContent).toContain("My Profile"));
  change(root, '[name="profile-name"]', "Night", "input");
  await vi.waitFor(() => expect(root.textContent).toMatch(/несохранён/i));
  click(root, "[data-create]");
  await vi.waitFor(() => expect(requests.some(({path, init}) => path.endsWith("/profiles") && init.method === "POST")).toBe(true));
  const create = requests.find(({path, init}) => path.endsWith("/profiles") && init.method === "POST")!;
  expect(JSON.parse(String(create.init.body))).toMatchObject({slug: "night", name: "Night", screen_mode: "Screen Splitting"});
  const cycle = get(root, '[data-profile="miku-cycle"]');
  await vi.waitFor(() => expect(get<HTMLButtonElement>(cycle, "[data-duplicate]").disabled).toBe(false));
  click(cycle, "[data-duplicate]");
  await vi.waitFor(() => expect(root.querySelector('[name="edit-profile-name"]')).toBeTruthy());
  change(root, '[name="edit-profile-name"]', "My Cycle", "input");
  await vi.waitFor(() => expect(get<HTMLButtonElement>(root, "[data-save-name]").disabled).toBe(false));
  click(root, "[data-save-name]");
  await vi.waitFor(() => expect(requests.some(({path}) => path.endsWith("/miku-cycle/duplicate"))).toBe(true));
  const custom = get(root, '[data-profile="custom"]');
  await vi.waitFor(() => expect(get<HTMLButtonElement>(custom, "[data-rename]").disabled).toBe(false));
  click(custom, "[data-rename]");
  await vi.waitFor(() => expect(root.querySelector('[name="edit-profile-name"]')).toBeTruthy());
  change(root, '[name="edit-profile-name"]', "Renamed", "input");
  await vi.waitFor(() => expect(get<HTMLButtonElement>(root, "[data-save-name]").disabled).toBe(false));
  click(root, "[data-save-name]");
  await vi.waitFor(() => expect(requests.some(({path, init}) => path.endsWith("/custom") && init.method === "PATCH" &&
    String(init.body) === '{"name":"Renamed"}')).toBe(true));
});

it("exports through the server, applies with a revision and confirms before delete", async () => {
  const {store, requests} = await setup((path, init) =>
    path.endsWith("/apply") ? json(mutation) :
    init.method === "DELETE" ? new Response(null, {status: 204}) : undefined);
  const root = await render(new ProfilesPage(), store);
  await vi.waitFor(() => expect(root.textContent).toContain("My Profile"));
  const custom = get(root, '[data-profile="custom"]');
  expect(get<HTMLAnchorElement>(custom, "[data-export]").getAttribute("href")).toBe("/api/v1/profiles/custom/export");
  click(custom, "[data-apply]");
  await vi.waitFor(() => expect(requests.find(({path}) => path.endsWith("/custom/apply"))).toBeDefined());
  const apply = requests.find(({path}) => path.endsWith("/custom/apply"))!;
  expect((apply.init.headers as Headers).get("If-Match")).toBe("4");
  await vi.waitFor(() => expect(get<HTMLButtonElement>(custom, "[data-delete]").disabled).toBe(false));
  click(custom, "[data-delete]");
  await vi.waitFor(() => expect(get(root, '[role="alertdialog"]').textContent).toContain("My Profile"));
  expect(requests.some(({init}) => init.method === "DELETE")).toBe(false);
  click(root, "[data-confirm-delete]");
  await vi.waitFor(() => expect(requests.some(({path, init}) => path.endsWith("/custom") && init.method === "DELETE")).toBe(true));
});

it("shows invalid import before sending and imports a valid JSON document", async () => {
  const {store, requests} = await setup((path) => path.endsWith("/import") ? json({profile: profiles[5]}, 201) : undefined);
  const root = await render(new ProfilesPage(), store);
  const input = get<HTMLInputElement>(root, '[name="profile-import"]');
  const choose = (text: string) => {
    Object.defineProperty(input, "files", {configurable: true, value: [new File([text], "profile.json")]});
    input.dispatchEvent(new Event("change"));
  };
  choose("[invalid]");
  await vi.waitFor(() => expect(get(root, '[role="alert"]').textContent).toMatch(/JSON/i));
  expect(requests.some(({path}) => path.endsWith("/import"))).toBe(false);
  choose('{"slug":"imported","name":"Imported"}');
  await vi.waitFor(() => expect(requests.find(({path}) => path.endsWith("/import"))?.init.body)
    .toBe('{"slug":"imported","name":"Imported"}'));
});
