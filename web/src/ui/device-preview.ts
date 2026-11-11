import {css, html, LitElement} from "lit";
import {customElement, property} from "lit/decorators.js";

import type {ScreenStateDocument} from "../api-types";

@customElement("device-preview")
export class DevicePreview extends LitElement {
  @property({attribute: false}) state!: ScreenStateDocument;

  static styles = css`
    :host { display: block; }
    figure { margin: 0; display: grid; gap: .65rem; }
    figcaption { color: #aeb9c9; font-size: .78rem; }
    .panel { aspect-ratio: 2240 / 1080; display: grid; grid-template-columns: 1fr; overflow: hidden; border: .55rem solid #202838; border-radius: 1.2rem; background: #070a11; box-shadow: inset 0 0 3rem #000, 0 1rem 2.5rem #0005; opacity: calc(var(--preview-opacity, 100) / 100); }
    .panel.split { grid-template-columns: 1fr 1fr; }
    .zone { display: grid; grid-template-columns: repeat(3, 1fr); gap: .35rem; padding: .7rem; border-right: 1px solid #ffffff18; background: radial-gradient(circle at 25% 0%, #153f4c, transparent 60%); }
    .slot { display: grid; place-content: center; min-width: 0; padding: .3rem; border-radius: .45rem; background: #111827c9; color: #fff; text-align: center; font-size: clamp(.5rem, 1.2vw, .78rem); overflow-wrap: anywhere; }
    .slot.off { opacity: .25; }
  `;

  protected render() {
    if (!this.state) return html``;
    const split = this.state.screen_mode === "Screen Splitting";
    const zones = split ? [this.state.slots.slice(0, 3), this.state.slots.slice(3, 6)] : [this.state.slots];
    return html`
      <figure aria-label="Предпросмотр расположения виджетов">
        <div class="panel ${split ? "split" : ""}" style=${`--preview-opacity:${this.state.opacity}`}>
          ${zones.map((slots) => html`<div class="zone">
            ${slots.map((slot) => html`<div class="slot ${slot.enabled ? "" : "off"}">${slot.enabled ? (slot.label || slot.widget) : "Пусто"}</div>`)}
          </div>`)}
        </div>
        <figcaption>Предпросмотр конфигурации — не снимок экрана</figcaption>
      </figure>
    `;
  }
}

declare global { interface HTMLElementTagNameMap { "device-preview": DevicePreview; } }
