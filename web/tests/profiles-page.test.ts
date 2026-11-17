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

it("creates from screen state and renames by server slug", async () => {
  const {store, requests} = await setup((path, init) => {
    if ((init.method === "POST" && path.endsWith("/profiles")) ||
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

it.each([
  {slug: "miku-cycle", name: "Miku Cycle"},
  {slug: "my-profile", name: "My Profile"},
])("keeps the suggested name and creates distinct copies of $name", async ({slug, name}) => {
  const available = profiles.map((profile) =>
    profile.slug === "custom" ? {...profile, slug: "my-profile"} : profile);
  const {store} = await setup((path, init) => {
    if (path === "/api/v1/profiles") return json({profiles: available});
    if (path !== `/api/v1/profiles/${slug}/duplicate` || init.method !== "POST") return;
    const destination = JSON.parse(String(init.body)) as {name: string; slug: string};
    if (available.some((profile) => profile.slug === destination.slug)) {
      return json({error: "conflict", message: `Slug already exists: ${destination.slug}`}, 409);
    }
    const original = available.find((profile) => profile.slug === slug)!;
    const copy = {...original, ...destination, factory: false};
    available.push(copy);
    return json({profile: copy}, 201);
  });
  const root = await render(new ProfilesPage(), store);
  const originalSelector = `[data-profile="${slug}"]`;
  await vi.waitFor(() => expect(root.querySelector(originalSelector)).toBeTruthy());
  for (const suffix of ["copy", "copy-2"]) {
    click(get(root, originalSelector), "[data-duplicate]");
    const nameInput = '[name="edit-profile-name"]';
    const suggest = `${name} (копия)`;
    await vi.waitFor(() => expect(get<HTMLInputElement>(root, nameInput)?.value).toBe(suggest));
    click(root, "[data-save-name]");
    await vi.waitFor(() => {
      const alert = root.querySelector('[role="alert"]');
      expect(alert?.textContent).toBeUndefined();
      expect(root.querySelector(`[data-profile="${slug}-${suffix}"] h3`)?.textContent).toBe(suggest);
      expect(root.querySelector(nameInput)).toBeNull();
    });
  }
  expect(get(root, `${originalSelector} h3`).textContent).toBe(name);
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
