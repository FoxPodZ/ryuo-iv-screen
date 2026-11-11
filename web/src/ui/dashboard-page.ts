import {css, html, LitElement, nothing} from "lit";
import {customElement, property} from "lit/decorators.js";

import type {MeasurementDocument} from "../api-types";
import type {AppView} from "../store";

const labels: Record<string, string> = {
  "cpu.temperature": "CPU",
  "cpu.power": "CPU Power",
  "gpu.temperature": "GPU",
  "gpu.vram.used": "VRAM",
  "gpu.power": "GPU Power",
  "fan.cpu": "CPU Fan",
  "fan.gpu": "GPU Fan",
};

const formatNumber = (value: number): string => Number.isInteger(value)
  ? String(value)
  : value.toFixed(1);

const formatMeasurement = (measurement: MeasurementDocument): string => {
  if (!measurement.available || measurement.value === null) return "Недоступно";
  const value = measurement.value;
  if (measurement.unit === "B" || measurement.unit === "bytes") return `${(value / (1024 ** 3)).toFixed(1)} GiB`;
  if (measurement.unit === "C") return `${formatNumber(value)} °C`;
  if (measurement.unit === "F") return `${formatNumber(value)} °F`;
  return `${formatNumber(value)} ${measurement.unit}`.trim();
};

const formatUptime = (seconds = 0): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}ч ${minutes}м`;
};

@customElement("dashboard-page")
export class DashboardPage extends LitElement {
  @property({attribute: false}) view!: AppView;

  static styles = css`
    :host { display: block; color: var(--ink, #f5f7fb); }
    .notice { margin: 0 0 1rem; padding: .8rem 1rem; border: 1px solid #eb5c9a66; border-radius: .8rem; background: #eb5c9a16; color: #ffc8df; }
    .loading { min-height: 40vh; display: grid; place-items: center; color: #a9b3c4; letter-spacing: .08em; text-transform: uppercase; }
    .hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(15rem, .65fr); gap: 1rem; margin-bottom: 1rem; }
    .panel { border: 1px solid #ffffff12; border-radius: 1rem; padding: 1.2rem; background: linear-gradient(145deg, #171b27e8, #0e111aee); box-shadow: 0 1rem 3rem #0006; }
    .device { position: relative; overflow: hidden; }
    .device::after { content: ""; position: absolute; inset: auto -10% -65% 45%; aspect-ratio: 1; border-radius: 50%; background: radial-gradient(circle, #54e8d64a, transparent 65%); pointer-events: none; }
    .eyebrow { color: #65e5d7; text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; font-weight: 700; }
    h1, h2, p { margin: 0; }
    h1 { margin-top: .45rem; font-size: clamp(1.6rem, 3vw, 2.7rem); line-height: 1; }
    h2 { margin-bottom: 1rem; font-size: 1rem; color: #c7cfdb; }
    .status { display: inline-flex; align-items: center; gap: .45rem; margin-top: .8rem; color: #b9c5d6; }
    .dot { width: .55rem; height: .55rem; border-radius: 50%; background: #5de3b1; box-shadow: 0 0 1rem #5de3b1; }
    .dot.offline { background: #f2647f; box-shadow: 0 0 1rem #f2647f; }
    dl { display: grid; grid-template-columns: 1fr auto; gap: .55rem 1rem; margin: 0; }
    dt { color: #8591a5; }
    dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(11.5rem, 1fr)); gap: .8rem; }
    .metric { min-height: 7.5rem; display: flex; flex-direction: column; justify-content: space-between; }
    .metric strong { font-size: 1.5rem; font-variant-numeric: tabular-nums; }
    .metric small { color: #8591a5; overflow-wrap: anywhere; }
    .unavailable strong { color: #f0a9c3; font-size: 1rem; }
    .screen { margin-top: 1rem; }
    .media { color: #dce4f0; overflow-wrap: anywhere; }
    @media (max-width: 720px) { .hero { grid-template-columns: 1fr; } .panel { padding: 1rem; } }
    @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; transition: none !important; } }
  `;

  protected render() {
    const snapshot = this.view?.snapshot;
    if (!snapshot) return html`<div class="loading" role="status">Загрузка телеметрии…</div>`;
    const {device, state, telemetry} = snapshot;
    return html`
      ${this.view.error ? html`<div class="notice" role="alert">${this.view.error}</div>` : nothing}
      <main aria-label="Сводка системы">
        <div class="hero">
          <section class="panel device" aria-label="Устройство">
            <span class="eyebrow">ROG Ryuo IV · Live</span>
            <h1>${device.model || "Ryuo IV"}</h1>
            <div class="status"><span class="dot ${device.connected ? "" : "offline"}"></span>${device.connected ? "Подключено" : "Нет соединения"} · ${device.health}</div>
          </section>
          <section class="panel" aria-label="Состояние демона">
            <h2>Daemon / HID</h2>
            <dl>
              <dt>Firmware</dt><dd>${device.firmware || "—"}</dd>
              <dt>Uptime</dt><dd>${formatUptime(device.uptime)}</dd>
              <dt>Last ACK</dt><dd>${device.last_ack ?? "—"}</dd>
              <dt>Reconnects</dt><dd>${device.reconnect_count ?? 0}</dd>
            </dl>
          </section>
        </div>
        <section aria-label="Телеметрия">
          <h2>Live telemetry</h2>
          <div class="grid">
            ${Object.entries(telemetry.measurements).map(([id, measurement]) => html`
              <article class="panel metric ${measurement.available ? "" : "unavailable"}">
                <span class="eyebrow">${labels[id] || id}</span>
                <strong>${formatMeasurement(measurement)}</strong>
                <small>${measurement.available ? (measurement.source || "Источник не указан") : (measurement.error || "Нет данных от датчика")}</small>
              </article>
            `)}
          </div>
        </section>
        <section class="panel screen" aria-label="Текущая конфигурация экрана">
          <h2>Screen state</h2>
          <dl>
            <dt>Profile</dt><dd>${state.active_profile || "Без профиля"}</dd>
            <dt>Layout</dt><dd>${state.screen_mode}</dd>
            <dt>Brightness</dt><dd>${state.brightness}%</dd>
            <dt>Media</dt><dd class="media">${state.media.flat().join(" · ") || "Не выбрано"}</dd>
          </dl>
        </section>
      </main>
    `;
  }
}

declare global { interface HTMLElementTagNameMap { "dashboard-page": DashboardPage; } }
