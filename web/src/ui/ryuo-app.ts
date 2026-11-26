import {css, html, LitElement} from "lit";
import {customElement, property, state} from "lit/decorators.js";

import {ApiClient, EventStream} from "../api";
import {AppStore, type AppView} from "../store";
import "./dashboard-page";
import "./login-view";
import "./screen-page";
import "./media-page";
import "./profiles-page";
import "./settings-page";

const tabs = {
  dashboard: "Dashboard", screen: "Экран", media: "Медиатека", profiles: "Профили", settings: "Настройки",
} as const;
type Page = keyof typeof tabs;

@customElement("ryuo-app")
export class RyuoApp extends LitElement {
  @property({attribute: false}) store: AppStore = new AppStore(new ApiClient(), new EventStream());
  @state() private view: Readonly<AppView> = this.store.value;
  @state() private page: Page = "dashboard";
  private unsubscribe?: () => void;

  static styles = css`
    :host { display: block; min-height: 100vh; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem clamp(1rem, 4vw, 3rem); border-bottom: 1px solid #ffffff10; background: #090c13dd; backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 2; }
    .brand { display: flex; align-items: center; gap: .7rem; font-weight: 850; letter-spacing: .03em; }
    .glyph { display: grid; place-items: center; width: 2rem; aspect-ratio: 1; border-radius: .65rem; color: #07110f; background: linear-gradient(145deg, #5be3d3, #f265a1); }
    nav { display: flex; flex-wrap: wrap; gap: .35rem; color: #99a6b9; font-size: .9rem; }
    nav button { padding: .4rem .55rem; border: 0; border-bottom: 2px solid transparent; color: #99a6b9; background: transparent; font: inherit; cursor: pointer; }
    nav button[aria-current="page"] { color: #f5f7fb; border-bottom-color: #5be3d3; }
    nav button:focus-visible { outline: 2px solid #5be3d3; outline-offset: 2px; }
    .stream { display: flex; align-items: center; gap: .45rem; color: #9da9ba; font-size: .8rem; }
    .stream::before { content: ""; width: .45rem; height: .45rem; border-radius: 50%; background: #f26c83; }
    .stream.live::before { background: #5de2b0; }
    main { width: min(78rem, calc(100% - 2rem)); margin: 1.2rem auto 3rem; }
    @media (max-width: 860px) { header { flex-wrap: wrap; } nav { order: 3; width: 100%; } }
    @media (max-width: 560px) { header { padding: .65rem .6rem; } nav { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); } nav button { padding-inline: .1rem; font-size: .8rem; } main { width: min(100% - 1rem, 78rem); } }
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
  `;

  connectedCallback(): void {
    super.connectedCallback();
    this.unsubscribe = this.store.subscribe((value) => { this.view = value; });
    void this.store.start();
  }

  disconnectedCallback(): void {
    this.unsubscribe?.();
    this.store.stop();
    super.disconnectedCallback();
  }

  protected render() {
    return html`
      <header>
        <div class="brand"><span class="glyph">IV</span> RYŪŌ SCREEN</div>
        ${this.view.phase !== "login" ? html`
          <nav aria-label="Основная навигация">
            ${(Object.keys(tabs) as Page[]).map((page) => html`
              <button type="button" aria-current=${this.page === page ? "page" : "false"}
                @click=${() => this.navigate(page)}>${tabs[page]}</button>`)}
          </nav>` : ""}
        <div class="stream ${this.view.connected ? "live" : ""}">${this.view.auth?.demo ? "Демонстрационные данные" : this.view.connected ? "Live" : "Offline"}</div>
      </header>
      <main>
        ${this.view.phase === "login"
          ? html`<login-view .view=${this.view} @login-submit=${this.onLogin}></login-view>`
          : this.renderPage()}
      </main>
    `;
  }

  private renderPage() {
    if (this.view.phase !== "ready") return html`<dashboard-page .view=${this.view}></dashboard-page>`;
    switch (this.page) {
      case "screen":
        return html`<screen-page .snapshot=${this.view.snapshot} .sensors=${this.view.sensors ?? []}
          .controller=${this.store} .mutationError=${this.view.mutationError ?? null}></screen-page>`;
      case "media":
        return html`<media-page .view=${this.view} .store=${this.store}></media-page>`;
      case "profiles":
        return html`<profiles-page .view=${this.view} .store=${this.store}></profiles-page>`;
      case "settings":
        return html`<settings-page .view=${this.view} .store=${this.store}></settings-page>`;
      case "dashboard":
        return html`<dashboard-page .view=${this.view}></dashboard-page>`;
    }
  }

  private navigate(page: Page): void {
    if (page === this.page) return;
    const editor = this.renderRoot.querySelector("media-page, profiles-page, settings-page") as
      (HTMLElement & {hasUnsavedChanges: boolean}) | null;
    if (editor?.hasUnsavedChanges && !window.confirm("Покинуть страницу и потерять несохранённые изменения?")) return;
    this.page = page;
  }

  private onLogin(event: CustomEvent<{password: string}>): void {
    void this.store.login(event.detail.password);
  }
}

declare global { interface HTMLElementTagNameMap { "ryuo-app": RyuoApp; } }
