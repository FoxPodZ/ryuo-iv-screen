import {beforeAll, describe, expect, it, vi} from "vitest";

import type {AppView} from "../src/store";

beforeAll(async () => {
  await import("../src/ui/login-view");
});

const loginView: AppView = {
  phase: "login",
  auth: {required: true, authenticated: false, csrfToken: null},
  csrfToken: null,
  snapshot: null,
  error: null,
  connected: false,
  lastEventId: 0,
  retryDelay: 500,
};

describe("login-view", () => {
  it("does not render when localhost authentication is not required", async () => {
    const element = document.createElement("login-view") as HTMLElement & {view: AppView; updateComplete: Promise<unknown>};
    element.view = {...loginView, phase: "ready", auth: {required: false, authenticated: true, csrfToken: null}};
    document.body.append(element);
    await element.updateComplete;
    expect(element.shadowRoot?.querySelector("input[type='password']")).toBeNull();
    element.remove();
  });

  it("emits a password only in a transient event and clears the input", async () => {
    const element = document.createElement("login-view") as HTMLElement & {view: AppView; updateComplete: Promise<unknown>};
    element.view = loginView;
    const listener = vi.fn();
    element.addEventListener("login-submit", listener);
    document.body.append(element);
    await element.updateComplete;
    const input = element.shadowRoot?.querySelector("input") as HTMLInputElement;
    input.value = "secret-password";
    input.dispatchEvent(new Event("input", {bubbles: true, composed: true}));
    const form = element.shadowRoot?.querySelector("form") as HTMLFormElement;
    form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0].detail.password).toBe("secret-password");
    expect(input.value).toBe("");
    expect(element.shadowRoot?.textContent).not.toContain("secret-password");
    element.remove();
  });

  it("shows failed and expired session errors clearly", async () => {
    const element = document.createElement("login-view") as HTMLElement & {view: AppView; updateComplete: Promise<unknown>};
    element.view = {...loginView, error: "Сессия истекла. Войдите снова."};
    document.body.append(element);
    await element.updateComplete;
    expect(element.shadowRoot?.querySelector("[role='alert']")?.textContent).toContain("Сессия истекла");
    element.remove();
  });
});
