import {css, html, LitElement, nothing} from "lit";
import {customElement, property} from "lit/decorators.js";

import type {AppView} from "../store";

@customElement("login-view")
export class LoginView extends LitElement {
  @property({attribute: false}) view!: AppView;

  static styles = css`
    :host { display: block; min-height: 70vh; display: grid; place-items: center; color: #f5f7fb; }
    .card { width: min(24rem, calc(100vw - 2rem)); padding: 1.6rem; border: 1px solid #ffffff16; border-radius: 1.2rem; background: #121722e8; box-shadow: 0 1.5rem 4rem #0008; }
    .mark { color: #61e5d6; text-transform: uppercase; font-size: .72rem; font-weight: 800; letter-spacing: .15em; }
    h1 { margin: .55rem 0 .5rem; font-size: 1.8rem; }
    p { color: #98a4b6; line-height: 1.5; }
    label { display: grid; gap: .45rem; margin-top: 1.2rem; color: #cdd4df; }
    input { color: #fff; background: #080b12; border: 1px solid #ffffff24; border-radius: .7rem; padding: .8rem; font: inherit; }
    input:focus-visible, button:focus-visible { outline: 3px solid #66e5d7; outline-offset: 2px; }
    button { width: 100%; margin-top: .85rem; padding: .8rem; border: 0; border-radius: .7rem; color: #07110f; background: linear-gradient(90deg, #5ce4d3, #79f0b6); font: inherit; font-weight: 800; cursor: pointer; }
    [role=alert] { color: #ffc2d8; padding: .7rem; border-radius: .6rem; background: #f2558c18; }
  `;

  protected render() {
    if (!this.view || this.view.phase !== "login" || !this.view.auth?.required) return nothing;
    return html`
      <section class="card" aria-labelledby="login-title">
        <span class="mark">Ryuo Control</span>
        <h1 id="login-title">Вход в LAN-панель</h1>
        <p>Пароль проверяется локальным сервисом и не сохраняется в интерфейсе.</p>
        ${this.view.error ? html`<p role="alert">${this.view.error}</p>` : nothing}
        <form @submit=${this.submit}>
          <label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>
          <button type="submit">Войти</button>
        </form>
      </section>
    `;
  }

  private submit(event: SubmitEvent): void {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem("password") as HTMLInputElement;
    const password = input.value;
    input.value = "";
    this.dispatchEvent(new CustomEvent("login-submit", {
      detail: {password},
      bubbles: true,
      composed: true,
    }));
  }
}

declare global {
  interface HTMLElementTagNameMap { "login-view": LoginView; }
  interface HTMLElementEventMap { "login-submit": CustomEvent<{password: string}>; }
}
