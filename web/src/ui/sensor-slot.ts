import {css, html, LitElement, nothing} from "lit";
import {customElement, property} from "lit/decorators.js";

import type {SlotAssignment} from "../api-types";
import type {SelectableSensor} from "../screen-model";

@customElement("sensor-slot")
export class SensorSlot extends LitElement {
  @property({attribute: false}) assignment: SlotAssignment = {
    enabled: false, measurement_id: "", widget: "", label: null,
  };
  @property({attribute: false}) options: readonly SelectableSensor[] = [];
  @property({type: Number}) index = 0;

  static styles = css`
    :host { display: block; }
    article { display: grid; gap: .55rem; padding: .8rem; border: 1px solid #ffffff16; border-radius: .8rem; background: #0c111bd9; }
    header { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
    strong { color: #67e5d7; }
    .moves { display: flex; gap: .3rem; }
    button, select, input { font: inherit; color: #eef4fb; background: #151c29; border: 1px solid #ffffff24; border-radius: .45rem; padding: .45rem; }
    button { min-width: 2rem; cursor: pointer; }
    button:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid #65e5d7; outline-offset: 2px; }
    label { display: grid; gap: .25rem; color: #a9b4c6; font-size: .82rem; }
    .meta { display: grid; gap: .2rem; color: #8f9bad; font-size: .72rem; overflow-wrap: anywhere; }
    .bad { color: #f2a8c2; }
  `;

  protected render() {
    const selected = this.options.find((item) => item.descriptor.measurementId === this.assignment.measurement_id);
    return html`
      <article draggable="true" @dragstart=${this.onDragStart} @dragover=${this.onDragOver} @drop=${this.onDrop}>
        <header>
          <strong>Слот ${this.index + 1}</strong>
          <span class="moves">
            <button type="button" aria-label="Переместить слот ${this.index + 1} вверх" ?disabled=${this.index === 0} @click=${() => this.move(-1)}>↑</button>
            <button type="button" aria-label="Переместить слот ${this.index + 1} вниз" ?disabled=${this.index === 5} @click=${() => this.move(1)}>↓</button>
          </span>
        </header>
        <label>Датчик
          <select .value=${this.assignment.enabled ? this.assignment.measurement_id : ""} @change=${this.onSensorChange}>
            <option value="">Отключён — позиция сохранена</option>
            ${this.options.map((option) => html`
              <option value=${option.descriptor.measurementId}>
                ${option.descriptor.label} · ${option.descriptor.ref.provider} · ${option.available ? "доступен" : "недоступен"}
              </option>
            `)}
          </select>
        </label>
        ${selected?.userLabelCapable ? html`
          <label>Пользовательская подпись
            <input name="slot_label" maxlength="48" .value=${this.assignment.label ?? selected.descriptor.label} @change=${this.onLabelChange}>
          </label>
        ` : nothing}
        ${selected ? html`
          <div class="meta ${selected.available ? "" : "bad"}">
            <span>${selected.descriptor.ref.provider} / ${selected.descriptor.ref.device}</span>
            <span>${selected.descriptor.source || "Источник не указан"}</span>
            ${selected.available ? nothing : html`<span>${selected.descriptor.error || "Датчик недоступен"}</span>`}
          </div>
        ` : nothing}
      </article>
    `;
  }

  private emit(name: string, detail: unknown): void {
    this.dispatchEvent(new CustomEvent(name, {detail, bubbles: true, composed: true}));
  }

  private move(delta: number): void {
    this.emit("slot-move", {from: this.index, to: this.index + delta});
  }

  private onDragStart(event: DragEvent): void {
    event.dataTransfer?.setData("text/plain", String(this.index));
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
    this.emit("slot-drag-start", {index: this.index});
  }

  private onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
  }

  private onDrop(event: DragEvent): void {
    event.preventDefault();
    this.emit("slot-drop", {index: this.index});
  }

  private onSensorChange(event: Event): void {
    const measurementId = (event.currentTarget as HTMLSelectElement).value;
    if (!measurementId) {
      this.emit("slot-change", {index: this.index, assignment: {...this.assignment, enabled: false}});
      return;
    }
    const selected = this.options.find((item) => item.descriptor.measurementId === measurementId);
    if (!selected) return;
    this.emit("slot-change", {
      index: this.index,
      assignment: {
        enabled: true,
        measurement_id: measurementId,
        widget: selected.widget,
        label: selected.userLabelCapable ? (this.assignment.label || selected.descriptor.label) : null,
      } satisfies SlotAssignment,
    });
  }

  private onLabelChange(event: Event): void {
    const label = (event.currentTarget as HTMLInputElement).value.trim();
    const selected = this.options.find((item) => item.descriptor.measurementId === this.assignment.measurement_id);
    if (!selected?.userLabelCapable) return;
    this.emit("slot-change", {
      index: this.index,
      assignment: {
        ...this.assignment,
        label: label || selected.descriptor.label,
        widget: `Fan Speed ${label || selected.descriptor.label}`,
      },
    });
  }
}

declare global { interface HTMLElementTagNameMap { "sensor-slot": SensorSlot; } }
