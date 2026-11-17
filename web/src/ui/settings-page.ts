import {html, LitElement, nothing, type PropertyValues} from "lit";
import {customElement, property, state} from "lit/decorators.js";
import {live} from "lit/directives/live.js";
import type {ScreenStateDocument, SensorDescriptorDocument, SensorRefDocument} from "../api-types";
import type {AppStore, AppView} from "../store";
import {libraryStyles} from "./library-styles";

type Selector = "gpu" | "motherboard";
type SettingsDraft = {
  refresh_interval: string;
  temperature_unit: ScreenStateDocument["temperature_unit"];
  sensor_selectors: Record<string, unknown>;
};
type Choice = {value: string; label: string; ref: SensorRefDocument};

function isRef(value: unknown): value is SensorRefDocument {
  return Boolean(value && typeof value === "object" &&
    "provider" in value && typeof value.provider === "string" &&
    "device" in value && typeof value.device === "string" &&
    "channel" in value && typeof value.channel === "string");
}
const refKey = ({provider, device, channel}: SensorRefDocument): string => JSON.stringify([provider, device, channel]);
const equipmentStatus = (available: boolean | undefined, label: string): string =>
  available === undefined ? `${label} · нет данных` : `${label} ${available ? "доступен" : "недоступен"}`;

function selectorChoices(kind: Selector, sensors: readonly SensorDescriptorDocument[]): Choice[] {
  const choices = new Map<string, Choice>();
  for (const sensor of sensors) {
    const {ref, measurementId, source, available, metadata} = sensor;
    if (kind === "gpu" && (ref.provider !== "amd" && ref.provider !== "nvidia" ||
        !measurementId.startsWith("gpu."))) continue;
    if (kind === "motherboard" && (ref.provider !== "hwmon" || measurementId !== "motherboard.temperature" ||
        !/^temp\d+$/.test(ref.channel))) continue;
    const value = kind === "gpu" ? JSON.stringify([ref.provider, ref.device]) : refKey(ref);
    if (choices.has(value)) continue;
    const name = kind === "gpu" && typeof metadata.name === "string" ? metadata.name : sensor.label;
    const label = kind === "gpu"
      ? `${ref.provider} · ${name} · ${ref.device}`
      : `${name} · ${ref.device}/${ref.channel}${!available ? " · недоступен" : ""}`;
    choices.set(value, {value, label, ref});
    if (kind === "motherboard" && !source) {
      // A missing persisted ref still belongs in the list.
      choices.set(value, {value, label: `${label} · нет источника`, ref});
    }
  }
  return [...choices.values()];
}

@customElement("settings-page")
export class SettingsPage extends LitElement {
  @property({attribute: false}) store?: AppStore;
  @property({attribute: false}) view?: Readonly<AppView>;
  @state() private draft?: SettingsDraft;
  @state() private dirty = false;
  @state() private busy = false;
  @state() private error = "";
  @state() private feedback = "";
  @state() private copied = "";
  private revision = -1;

  static styles = libraryStyles;

  get hasUnsavedChanges(): boolean { return this.dirty; }

  connectedCallback(): void {
    super.connectedCallback();
    this.refresh();
  }

  protected willUpdate(changes: PropertyValues<this>): void {
    if (changes.has("view") && !this.dirty && this.view?.snapshot?.revision !== this.revision) this.reset();
  }

  private refresh(): void {
    void this.store?.ensureSensors(true);
    void this.store?.loadMedia();
    void this.store?.loadDiagnostics();
  }

  private reset(): void {
    const snapshot = this.view?.snapshot;
    if (!snapshot) return;
    const {refresh_interval, temperature_unit, sensor_selectors} = snapshot.state;
    this.draft = {refresh_interval: String(refresh_interval), temperature_unit, sensor_selectors};
    this.revision = snapshot.revision;
    this.dirty = false;
  }

  private edit(changes: Partial<SettingsDraft>): void {
    if (!this.draft) return;
    this.draft = {...this.draft, ...changes};
    this.dirty = true;
    this.feedback = "";
  }

  private select(kind: Selector, ref: SensorRefDocument | undefined): void {
    const selector = {...this.draft?.sensor_selectors};
    if (ref) selector[kind] = ref;
    else delete selector[kind];
    this.edit({sensor_selectors: selector});
  }

  private async save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!this.store || !this.draft || !this.dirty || this.busy) return;
    const refresh_interval = Number(this.draft.refresh_interval);
    if (!Number.isFinite(refresh_interval) || refresh_interval <= 0 || refresh_interval > 60) {
      this.error = "Интервал должен быть больше 0 и не более 60 секунд";
      return;
    }
    this.busy = true;
    this.error = "";
    try {
      const result = await this.store.patchScreen("telemetry-settings", {...this.draft, refresh_interval}, this.revision);
      if (result.ok) {
        this.reset();
        this.feedback = "Настройки сохранены и поставлены в очередь";
      } else if (result.error) {
        this.error = result.error;
      }
    } finally {
      this.busy = false;
    }
  }

  private get diagnosticsText(): string {
    const data = this.view?.diagnostics;
    const snapshot = this.view?.snapshot;
    const catalog = this.view?.media;
    // Enumerate the safe fields. Never serialize a whole API response or its free-text errors.
    return JSON.stringify({
      security: data ? {
        bindMode: data.security.bindMode,
        lanEnabled: data.security.lanEnabled,
        authenticationRequired: data.security.authenticationRequired,
        trustedProxyCount: data.security.trustedProxyCount,
        activeSessions: data.security.sessions.active,
        sessionCapacity: data.security.sessions.capacity,
      } : null,
      session: data ? {
        required: data.session.required, authenticated: data.session.authenticated,
        expiresIn: data.session.expiresIn,
      } : null,
      media: catalog ? {
        adb: catalog.adb.available, ffmpeg: catalog.tools.ffmpeg, ffprobe: catalog.tools.ffprobe,
      } : null,
      device: snapshot ? {connected: snapshot.device.connected} : null,
      state: snapshot ? {revision: snapshot.revision, interval: snapshot.state.refresh_interval,
        temperatureUnit: snapshot.state.temperature_unit, streamConnected: this.view?.connected} : null,
      telemetry: snapshot ? {
        sampled: snapshot.telemetry.sampledAt !== null,
        availableCount: Object.values(snapshot.telemetry.measurements).filter((item) => item.available).length,
        errorCount: Object.keys(snapshot.telemetry.errors).length,
      } : null,
    }, null, 2);
  }

  private async copyDiagnostics(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.diagnosticsText);
      this.copied = "Диагностика скопирована";
    } catch {
      const textarea = this.renderRoot.querySelector("textarea");
      textarea?.focus();
      textarea?.select();
      this.copied = "Нажмите Ctrl+C или ⌘C, чтобы скопировать выделенный текст";
    }
  }

  protected render() {
    const data = this.view?.diagnostics;
    const catalog = this.view?.media;
    const snapshot = this.view?.snapshot;
    const errors = Object.values(snapshot?.telemetry.errors ?? {});
    const measurements = Object.entries(snapshot?.telemetry.measurements ?? {});
    const current = [
      ["CPU", measurements.find(([name, item]) => name.startsWith("cpu.") && item.available)?.[1]],
      ["GPU", measurements.find(([name, item]) => name.startsWith("gpu.") && item.available)?.[1]],
      ["Материнская плата", snapshot?.telemetry.measurements["motherboard.temperature"]],
    ] as const;

    return html`
      <section class="page" aria-labelledby="settings-heading">
        <div class="row">
          <h1 id="settings-heading">Настройки</h1>
          <button type="button" @click=${this.refresh}>Обновить диагностику</button>
        </div>
        <div class="columns">
          <section class="panel stack" aria-labelledby="source-heading">
            <h2 id="source-heading">Текущие источники телеметрии</h2>
            <dl>${current.map(([name, item]) => html`
              <dt>${name}</dt><dd>${isRef(item?.ref) ? item.ref.provider + " · " : ""}
                ${item?.available ? item.source || "Источник не указан" : item?.error || "Данные недоступны"}</dd>`)}
            </dl>
            ${errors.length ? html`<ul class="muted">${errors.map((error) => html`<li>${error}</li>`)}</ul>` : nothing}
          </section>
          ${this.draft ? html`
            <form class="panel stack" aria-labelledby="telemetry-settings-title" @submit=${this.save}>
              <h2 id="telemetry-settings-title">Настройки телеметрии</h2>
              ${this.renderSelector("gpu", "Провайдер и устройство GPU")}
              ${this.renderSelector("motherboard", "Датчик материнской платы")}
              <label>Интервал обновления, с
                <input type="number" name="refresh_interval" required min="0.001" max="60" step="any"
                  .value=${live(this.draft.refresh_interval)} @input=${(event: Event) => {
                    this.edit({refresh_interval: (event.currentTarget as HTMLInputElement).value});
                  }}>
              </label>
              <label>Единица температуры
                <select name="temperature_unit" @change=${(event: Event) => {
                  this.edit({temperature_unit: (event.currentTarget as HTMLSelectElement).value as SettingsDraft["temperature_unit"]});
                }}>
                  <option value="Celsius" .selected=${live(this.draft.temperature_unit === "Celsius")}>°C</option>
                  <option value="Fahrenheit" .selected=${live(this.draft.temperature_unit === "Fahrenheit")}>°F</option>
                </select>
              </label>
              ${this.dirty && snapshot?.revision !== this.revision ? html`
                <p class="notice" role="status">Конфигурация изменилась. Сбросьте черновик до актуальной версии.</p>` : nothing}
              ${this.error ? html`<p class="error" role="alert">${this.error}</p>` : nothing}
              ${this.feedback ? html`<p class="active" role="status">${this.feedback}</p>` : nothing}
              <div class="actions">
                <button type="submit" class="primary" data-save-settings ?disabled=${!this.dirty || this.busy ||
                  snapshot?.revision !== this.revision}>Сохранить</button>
                ${this.dirty ? html`<button type="button" ?disabled=${this.busy} @click=${this.reset}>Сбросить черновик</button>` : nothing}
              </div>
            </form>` : html`<p role="status">Загрузка настроек телеметрии…</p>`}
        </div>
        <div class="columns">
          <section class="panel stack" aria-labelledby="availability-title">
            <h2 id="availability-title">Инструменты</h2>
            <ul>
              <li>${equipmentStatus(catalog?.adb.available, "ADB")}</li>
              <li>${equipmentStatus(catalog?.tools.ffmpeg, "FFmpeg")}</li>
              <li>${equipmentStatus(catalog?.tools.ffprobe, "FFprobe")}</li>
            </ul>
            ${this.view?.mediaError ? html`<p class="error" role="alert">${this.view.mediaError}</p>` : nothing}
          </section>
          <section class="panel stack" aria-labelledby="access-title">
            <h2 id="access-title">Доступ и сессия</h2>
            ${data ? html`
              <dl>
                <dt>Настроенный режим прослушивания</dt><dd>${data.security.bindMode === "lan" ? "LAN" : "Только loopback"}</dd>
                <dt>Авторизация</dt><dd>${data.security.authenticationRequired ? "Пароль настроен" :
                  data.security.trustedProxyCount ? "Доверенный прокси" : "Локальный доступ"}</dd>
                <dt>Текущая сессия</dt><dd>${data.session.required
                  ? data.session.authenticated ? "Активна" : "Вход требуется" : "Для этого подключения вход не требуется"}</dd>
                <dt>Сессий сервера</dt><dd>${data.security.sessions.active} / ${data.security.sessions.capacity}</dd>
              </dl>` : html`<p role="status">${this.view?.diagnosticsError || "Загрузка статуса доступа…"}</p>`}
            <p class="muted">Адрес прослушивания и пароль меняются в системном файле
              <code>/etc/ryuo-screen/config.toml</code>. Изменения вступают в силу после перезапуска службы.</p>
          </section>
        </div>
        <section class="panel stack" aria-labelledby="diagnostics-title">
          <div class="row"><h2 id="diagnostics-title">Диагностика</h2>
            <button type="button" data-copy-diagnostics @click=${this.copyDiagnostics}>Копировать диагностику</button>
          </div>
          <textarea readonly rows="8" aria-label="Диагностика без секретов" .value=${this.diagnosticsText}></textarea>
          ${this.copied ? html`<p role="status">${this.copied}</p>` : nothing}
        </section>
      </section>
    `;
  }

  private renderSelector(kind: Selector, label: string) {
    const saved = this.draft?.sensor_selectors[kind];
    const choices = selectorChoices(kind, this.view?.sensors ?? []);
    const value = isRef(saved) ? kind === "gpu" ? JSON.stringify([saved.provider, saved.device]) : refKey(saved) : "";
    if (isRef(saved) && !choices.some((item) => item.value === value)) {
      choices.push({value, label: `${saved.provider} · ${saved.device} · ${saved.channel} · недоступен`, ref: saved});
    }
    return html`
      <label>${label}
        <select name=${kind} @change=${(event: Event) => {
          const selected = (event.currentTarget as HTMLSelectElement).value;
          this.select(kind, choices.find((item) => item.value === selected)?.ref);
        }}>
          <option value="" .selected=${live(!value)}>По настройкам службы</option>
          ${choices.map((item) => html`<option value=${item.value} .selected=${live(item.value === value)}>${item.label}</option>`)}
        </select>
      </label>
    `;
  }
}
declare global { interface HTMLElementTagNameMap { "settings-page": SettingsPage; } }
