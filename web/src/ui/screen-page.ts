import {css, html, LitElement, nothing, type PropertyValues} from "lit";
import {customElement, property, state} from "lit/decorators.js";

import type {ScreenPatchKind} from "../api";
import type {
  ScreenStateDocument,
  SensorDescriptorDocument,
  ScreenMutationOutcome,
  SlotAssignment,
  SnapshotDocument,
} from "../api-types";
import {
  cloneScreenState,
  normalizeSlots,
  reorderSlots,
  screenModeState,
  selectableSensors,
} from "../screen-model";
import "./device-preview";
import "./sensor-slot";

export interface ScreenController {
  ensureSensors(): Promise<void>;
  patchScreen(kind: ScreenPatchKind, changes: Record<string, unknown>): Promise<ScreenMutationOutcome>;
}

const blankState = (): ScreenStateDocument => ({
  schema_version: 1,
  revision: 0,
  active_profile: null,
  screen_mode: "Full Screen",
  media: [[]],
  playback_modes: ["Single"],
  slots: normalizeSlots([]),
  brightness: 85,
  temperature_unit: "Celsius",
  refresh_interval: 1,
  title_colors: ["#E5252B"],
  content_colors: ["#FFFFFF"],
  opacity: 100,
  rgb_mode: "off",
  rgb_target: "value",
  thermal_source: "cpu.temperature",
  sensor_selectors: {},
});

@customElement("screen-page")
export class ScreenPage extends LitElement {
  @property({attribute: false}) snapshot: SnapshotDocument | null = null;
  @property({attribute: false}) sensors: readonly SensorDescriptorDocument[] = [];
  @property({attribute: false}) controller!: ScreenController;
  @property({attribute: false}) mutationError: string | null = null;
  @state() draft: ScreenStateDocument = blankState();
  @state() private fullRestart = false;
  private dragFrom: number | null = null;
  private draftRevision = -1;
  private patchTimer: number | null = null;
  private readonly pending = new Map<ScreenPatchKind, Record<string, unknown>>();

  static styles = css`
    :host { display: block; color: #f5f7fb; }
    .page { display: grid; gap: 1rem; }
    .heading { display: flex; justify-content: space-between; gap: 1rem; align-items: end; }
    h1, h2, p { margin: 0; }
    h1 { font-size: clamp(1.5rem, 3vw, 2.4rem); }
    .muted { color: #91a0b5; }
    .layout { display: grid; grid-template-columns: minmax(19rem, .9fr) minmax(24rem, 1.35fr); gap: 1rem; align-items: start; }
    .panel { border: 1px solid #ffffff14; border-radius: 1rem; padding: 1rem; background: linear-gradient(145deg, #151a27eb, #0d111aee); box-shadow: 0 1rem 2.5rem #0004; }
    .preview { position: sticky; top: 5.5rem; display: grid; gap: 1rem; }
    .controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .8rem; }
    fieldset { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .7rem; margin: 0; padding: .8rem; border: 1px solid #ffffff16; border-radius: .8rem; }
    legend { padding: 0 .35rem; color: #67e5d7; }
    label { display: grid; gap: .3rem; color: #aeb9c9; font-size: .82rem; }
    input, select { width: 100%; min-width: 0; padding: .55rem; border: 1px solid #ffffff24; border-radius: .5rem; color: #f5f7fb; background: #111827; font: inherit; }
    input[type="color"] { min-height: 2.65rem; padding: .25rem; }
    input:focus-visible, select:focus-visible { outline: 2px solid #65e5d7; outline-offset: 2px; }
    .slots { display: grid; gap: .65rem; margin-top: .8rem; }
    .alert { padding: .75rem .9rem; border: 1px solid #f26ca066; border-radius: .7rem; color: #ffc8df; background: #ed5d9214; }
    .restart { border-color: #f1b35b66; color: #ffd9a1; background: #e99b3112; }
    @media (max-width: 880px) { .layout { grid-template-columns: 1fr; } .preview { position: static; } }
    @media (max-width: 560px) { .controls, fieldset { grid-template-columns: 1fr; } .heading { align-items: start; flex-direction: column; } }
  `;

  connectedCallback(): void {
    super.connectedCallback();
    void this.controller?.ensureSensors();
  }

  disconnectedCallback(): void {
    if (this.patchTimer !== null) window.clearTimeout(this.patchTimer);
    this.patchTimer = null;
    this.pending.clear();
    super.disconnectedCallback();
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("snapshot") && this.snapshot && this.snapshot.state.revision !== this.draftRevision) {
      this.draft = cloneScreenState(this.snapshot.state);
      this.draftRevision = this.snapshot.state.revision;
      this.fullRestart = false;
    }
  }

  protected render() {
    const options = selectableSensors(this.sensors);
    const zones = this.draft.screen_mode === "Screen Splitting" ? 2 : 1;
    return html`
      <section class="page" aria-labelledby="screen-heading">
        <div class="heading">
          <div>
            <p class="muted">Ryuo IV · Screen composer</p>
            <h1 id="screen-heading">Экран и шесть слотов</h1>
          </div>
          <p class="muted">Revision ${this.draft.revision}</p>
        </div>
        ${this.mutationError ? html`<div class="alert" role="alert">${this.mutationError}</div>` : nothing}
        ${this.fullRestart ? html`<div class="alert restart" data-full-restart>Изменение media или режима перезапустит воспроизведение полной конфигурацией.</div>` : nothing}
        <div class="layout">
          <aside class="panel preview" aria-label="Предпросмотр">
            <p class="muted">Предпросмотр конфигурации — не снимок экрана</p>
            <device-preview .state=${this.draft}></device-preview>
            <div class="controls">
              <label>Режим экрана
                <select name="screen_mode" .value=${this.draft.screen_mode} @change=${this.onMode}>
                  <option>Full Screen</option><option>Screen Splitting</option>
                </select>
              </label>
              <label>Яркость
                <input name="brightness" type="range" min="0" max="102" step="1" .value=${String(this.draft.brightness)} @input=${this.onBrightness}>
              </label>
              <label>Единица температуры
                <select name="temperature_unit" .value=${this.draft.temperature_unit} @change=${this.onUnit}>
                  <option>Celsius</option><option>Fahrenheit</option>
                </select>
              </label>
              <label>Интервал, сек
                <input name="refresh_interval" type="number" min="0.1" max="60" step="0.1" .value=${String(this.draft.refresh_interval)} @change=${this.onInterval}>
              </label>
              <label>Прозрачность
                <input name="opacity" type="range" min="0" max="100" step="1" .value=${String(this.draft.opacity)} @input=${this.onOpacity}>
              </label>
              <label>RGB режим
                <select name="rgb_mode" .value=${this.draft.rgb_mode} @change=${this.onRgbMode}>
                  <option value="off">Off</option><option value="hue">Hue</option><option value="thermal">Thermal</option>
                </select>
              </label>
              <label>RGB цель
                <select name="rgb_target" .value=${this.draft.rgb_target} @change=${this.onRgbTarget}>
                  <option value="title">Title</option><option value="value">Value</option><option value="both">Both</option>
                </select>
              </label>
              <label>Thermal source
                <select name="thermal_source" .value=${this.draft.thermal_source} @change=${this.onThermalSource}>
                  ${options.filter((item) => item.descriptor.unit === "°C" || item.descriptor.unit === "C").map((item) => html`
                    <option value=${item.descriptor.measurementId}>${item.descriptor.label}</option>
                  `)}
                </select>
              </label>
              <fieldset>
                <legend>Цвета зон</legend>
                ${Array.from({length: zones}, (_, zone) => html`
                  <label>Заголовок ${zone + 1}<input type="color" name=${`title_color_${zone}`} .value=${this.draft.title_colors[zone]} @input=${(event: Event) => this.onColor(event, "title_colors", zone)}></label>
                  <label>Значение ${zone + 1}<input type="color" name=${`content_color_${zone}`} .value=${this.draft.content_colors[zone]} @input=${(event: Event) => this.onColor(event, "content_colors", zone)}></label>
                `)}
              </fieldset>
            </div>
          </aside>
          <section class="panel" aria-label="Редактор слотов">
            <h2>Позиции датчиков</h2>
            <p class="muted">Отключение сохраняет позицию. Перетаскивайте карточки или используйте кнопки со стрелками.</p>
            <p class="muted">${options.map((item) => `${item.descriptor.ref.provider}/${item.descriptor.ref.device}: ${item.available ? "доступен" : (item.descriptor.error || "недоступен")}`).join(" · ")}</p>
            <div class="slots" @slot-change=${this.onSlotChange} @slot-move=${this.onSlotMove} @slot-drag-start=${this.onSlotDragStart} @slot-drop=${this.onSlotDrop}>
              ${this.draft.slots.map((slot, index) => html`
                <sensor-slot
                  aria-label=${`Слот ${index + 1}: ${slot.enabled ? (slot.label || slot.widget) : "отключён"}`}
                  .assignment=${slot}
                  .options=${options}
                  .index=${index}>
                </sensor-slot>
              `)}
            </div>
          </section>
        </div>
      </section>
    `;
  }

  private queue(kind: ScreenPatchKind, changes: Record<string, unknown>): void {
    this.pending.set(kind, {...(this.pending.get(kind) ?? {}), ...changes});
    if (this.patchTimer !== null) window.clearTimeout(this.patchTimer);
    this.patchTimer = window.setTimeout(() => { void this.flush(); }, 160);
  }

  private async flush(): Promise<void> {
    this.patchTimer = null;
    const pending = [...this.pending.entries()];
    this.pending.clear();
    for (const [kind, changes] of pending) {
      const outcome = await this.controller.patchScreen(kind, changes);
      if (!outcome.ok) break;
    }
  }

  private onBrightness(event: Event): void {
    const brightness = Number((event.currentTarget as HTMLInputElement).value);
    this.draft = {...this.draft, brightness};
    this.queue("brightness", {brightness});
  }

  private onOpacity(event: Event): void {
    const opacity = Number((event.currentTarget as HTMLInputElement).value);
    this.draft = {...this.draft, opacity};
    this.queue("screen", {opacity});
  }

  private onUnit(event: Event): void {
    const temperature_unit = (event.currentTarget as HTMLSelectElement).value as "Celsius" | "Fahrenheit";
    this.draft = {...this.draft, temperature_unit};
    this.queue("telemetry-settings", {temperature_unit});
  }

  private onInterval(event: Event): void {
    const refresh_interval = Number((event.currentTarget as HTMLInputElement).value);
    if (!(refresh_interval > 0 && refresh_interval <= 60)) return;
    this.draft = {...this.draft, refresh_interval};
    this.queue("telemetry-settings", {refresh_interval});
  }

  private onMode(event: Event): void {
    const screenMode = (event.currentTarget as HTMLSelectElement).value as "Full Screen" | "Screen Splitting";
    this.draft = screenModeState(this.draft, screenMode);
    this.fullRestart = true;
    this.queue("screen", {
      screen_mode: this.draft.screen_mode,
      media: this.draft.media,
      playback_modes: this.draft.playback_modes,
      title_colors: this.draft.title_colors,
      content_colors: this.draft.content_colors,
    });
  }

  private onColor(event: Event, field: "title_colors" | "content_colors", zone: number): void {
    const colors = [...this.draft[field]];
    colors[zone] = (event.currentTarget as HTMLInputElement).value.toUpperCase();
    this.draft = {...this.draft, [field]: colors};
    this.queue("screen", {[field]: colors});
  }

  private onRgbMode(event: Event): void {
    const rgb_mode = (event.currentTarget as HTMLSelectElement).value;
    this.draft = {...this.draft, rgb_mode};
    this.queue("screen", {rgb_mode});
  }

  private onRgbTarget(event: Event): void {
    const rgb_target = (event.currentTarget as HTMLSelectElement).value;
    this.draft = {...this.draft, rgb_target};
    this.queue("screen", {rgb_target});
  }

  private onThermalSource(event: Event): void {
    const thermal_source = (event.currentTarget as HTMLSelectElement).value;
    this.draft = {...this.draft, thermal_source};
    this.queue("screen", {thermal_source});
  }

  private onSlotChange(event: CustomEvent<{index: number; assignment: SlotAssignment}>): void {
    const slots = normalizeSlots(this.draft.slots);
    slots[event.detail.index] = {...event.detail.assignment};
    this.draft = {...this.draft, slots};
    this.queue("screen", {slots});
  }

  private onSlotMove(event: CustomEvent<{from: number; to: number}>): void {
    const slots = reorderSlots(this.draft.slots, event.detail.from, event.detail.to);
    this.draft = {...this.draft, slots};
    this.queue("screen", {slots});
  }

  private onSlotDragStart(event: CustomEvent<{index: number}>): void {
    this.dragFrom = event.detail.index;
  }

  private onSlotDrop(event: CustomEvent<{index: number}>): void {
    if (this.dragFrom === null) return;
    const from = this.dragFrom;
    this.dragFrom = null;
    this.onSlotMove(new CustomEvent("slot-move", {detail: {from, to: event.detail.index}}));
  }
}

declare global { interface HTMLElementTagNameMap { "screen-page": ScreenPage; } }
