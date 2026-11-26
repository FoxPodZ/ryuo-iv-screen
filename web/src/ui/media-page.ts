import {css, html, LitElement, nothing, type PropertyValues} from "lit";
import {customElement, property, state} from "lit/decorators.js";
import {live} from "lit/directives/live.js";
import {mediaPreviewUrl} from "../api";
import {moveMedia, playbackModes, playlistFromState, type Playlist} from "../media-model";
import type {AppStore, AppView} from "../store";
import {libraryStyles} from "./library-styles";
import "./upload-zone";

@customElement("media-page")
export class MediaPage extends LitElement {
  @property({attribute: false}) store?: AppStore;
  @property({attribute: false}) view?: Readonly<AppView>;
  @state() private draft?: Playlist;
  @state() private dirty = false;
  @state() private busy = false;
  @state() private deleting: string | null = null;
  @state() private preview: {name: string; kind: "proxy" | "thumbnail"} | null = null;
  @state() private previewFailed = false;
  @state() private error = "";
  @state() private feedback = "";
  private revision = -1;

  static styles = [libraryStyles, css`
    fieldset { margin: 0; min-width: 0; }
    legend { padding: 0 .4rem; color: #6be9d8; }
    .zones > h2 { grid-column: 1 / -1; }
    .preview img, .preview video { display: block; max-width: min(100%, 40rem); max-height: 24rem; background: #080a10; border-radius: .65rem; }
    ol li + li { margin-top: .55rem; }
    .files .mono { font-size: .85rem; }
  `];

  get hasUnsavedChanges(): boolean { return this.dirty; }

  connectedCallback(): void {
    super.connectedCallback();
    void this.store?.loadMedia();
  }

  protected willUpdate(changes: PropertyValues<this>): void {
    const snapshot = this.view?.snapshot;
    if (changes.has("view") && snapshot && !this.dirty && snapshot.revision !== this.revision) {
      this.draft = playlistFromState(snapshot.state);
      this.revision = snapshot.revision;
    }
  }

  private edit(zone: number, changes: {items?: string[]; mode?: string}): void {
    if (!this.draft) return;
    const {items} = changes;
    const mode = items?.length === 0 ? "Single" : changes.mode;
    this.draft = {
      media: this.draft.media.map((old, index) => index === zone && items ? items : old),
      playback_modes: this.draft.playback_modes.map((old, index) => index === zone && mode ? mode : old),
    };
    this.dirty = true;
    this.feedback = "";
  }

  private reset(): void {
    const snapshot = this.view?.snapshot;
    if (!snapshot) return;
    this.draft = playlistFromState(snapshot.state);
    this.revision = snapshot.revision;
    this.dirty = false;
  }

  private async save(): Promise<void> {
    if (!this.draft || !this.store || this.busy) return;
    this.busy = true;
    this.error = "";
    try {
      const result = await this.store.patchScreen("screen", {...this.draft}, this.revision);
      if (result.ok) {
        this.reset();
        this.feedback = "Плейлисты сохранены и поставлены в очередь";
      } else if (result.error) {
        this.error = result.error;
      }
    } finally {
      this.busy = false;
    }
  }

  private async removeMedia(): Promise<void> {
    const name = this.deleting;
    if (!name || !this.store || this.busy) return;
    this.busy = true;
    this.error = "";
    try {
      await this.store.deleteMedia(name);
      if (this.preview?.name === name) this.preview = null;
      this.deleting = null;
      this.feedback = `Удаление подтверждено · ${name}`;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка удаления";
    } finally {
      this.busy = false;
    }
  }

  private showPreview(name: string, kind: "thumbnail" | "proxy"): void {
    this.preview = {name, kind};
    this.previewFailed = false;
  }

  protected render() {
    const library = this.view?.media;
    const factory = library?.factory ?? [];
    const custom = (library?.custom ?? []).filter((name) => !factory.includes(name));
    const available = Boolean(library?.adb.available && library.tools.ffmpeg);
    const uploadEnabled = Boolean(library?.adb.available && library.tools.ffprobe);
    const state = this.view?.snapshot?.state;
    const catalog = [...factory, ...custom];

    return html`
      <section class="page" aria-labelledby="media-heading">
        <div class="row">
          <h1 id="media-heading">Медиатека</h1>
          <button type="button" @click=${() => this.store?.loadMedia()}>Обновить список</button>
        </div>
        ${!library && !this.view?.mediaError ? html`<p role="status">Загрузка медиатеки…</p>` : nothing}
        ${this.view?.mediaError ? html`<p class="error" role="alert">${this.view.mediaError}</p>` : nothing}
        ${this.error ? html`<p class="error" role="alert">${this.error}</p>` : nothing}
        ${this.feedback ? html`<p class="active" role="status">${this.feedback}</p>` : nothing}
        ${library?.adb.available && library.adb.serial ? html`<p>Устройство ADB · <code>${library.adb.serial}</code></p>` : nothing}
        ${library && !library.adb.available ? html`<p class="notice" role="status">ADB недоступен · загрузка и предпросмотр отключены. ${library.adb.reason}</p>` : nothing}
        ${library && !library.tools.ffmpeg ? html`<p class="notice" role="status">FFmpeg недоступен · предпросмотр и конвертация отключены.</p>` : nothing}
        ${library && !library.tools.ffprobe ? html`<p class="notice" role="status">FFprobe недоступен · загрузка отключена.</p>` : nothing}
        <div class="columns">
          ${this.renderCatalog("Заводские файлы", factory, false, available)}
          ${this.renderCatalog("Пользовательские файлы", custom, true, available)}
        </div>
        ${this.deleting ? html`
          <section role="alertdialog" aria-labelledby="delete-media-title" aria-describedby="delete-media-description" class="panel stack">
            <h2 id="delete-media-title">Удалить пользовательский файл?</h2>
            <p id="delete-media-description" class="mono">${this.deleting}</p>
            ${state?.media.flat().includes(this.deleting) ? html`<p class="notice">Файл указан в текущем плейлисте.</p>` : nothing}
            <div class="actions">
              <button type="button" ?disabled=${this.busy} @click=${() => {this.deleting = null;}}>Отмена</button>
              <button type="button" data-confirm-delete class="danger" ?disabled=${this.busy} @click=${this.removeMedia}>Удалить</button>
            </div>
          </section>` : nothing}
        ${this.preview && available ? html`
          <section class="panel stack preview" aria-labelledby="preview-heading">
            <div class="row"><h2 id="preview-heading">Предпросмотр · ${this.preview.name}</h2>
              <button type="button" @click=${() => {this.preview = null;}}>Закрыть</button>
            </div>
            ${this.previewFailed ? html`<p class="error" role="alert">Сервер не смог создать предпросмотр.</p>` : nothing}
            ${this.preview.kind === "proxy"
              ? html`<video controls preload="metadata" aria-label=${this.preview.name}
                  src=${mediaPreviewUrl("proxy", this.preview.name)} @error=${() => {this.previewFailed = true;}}></video>`
              : html`<img alt=${this.preview.name} src=${mediaPreviewUrl("thumbnail", this.preview.name)}
                  @error=${() => {this.previewFailed = true;}}>`}
          </section>` : nothing}
        <upload-zone .store=${this.store} .view=${this.view} .disabled=${!uploadEnabled}></upload-zone>
        ${this.draft ? html`
          <section class="stack" aria-labelledby="playlist-title">
            <div class="row"><h2 id="playlist-title">Плейлисты</h2><p class="muted">${state?.screen_mode}</p></div>
            <div class="columns zones">
              ${this.draft.media.map((items, zone) => this.renderZone(items, zone, catalog))}
            </div>
            ${this.dirty ? html`
              <p class="notice" role="status">${this.view?.snapshot?.revision !== this.revision
                ? "Конфигурация изменилась. Сбросьте черновик до актуальной версии."
                : "Есть несохранённые изменения. Сохранение перезапустит воспроизведение."}</p>
            ` : nothing}
            <div class="actions">
              <button type="button" class="primary" data-save-playlists ?disabled=${!this.dirty || this.busy ||
                  this.view?.snapshot?.revision !== this.revision} @click=${this.save}>Сохранить плейлисты</button>
              ${this.dirty ? html`<button type="button" ?disabled=${this.busy} @click=${this.reset}>Сбросить черновик</button>` : nothing}
            </div>
          </section>` : nothing}
      </section>
    `;
  }

  private renderCatalog(title: string, names: readonly string[], custom: boolean, previewAvailable: boolean) {
    return html`
      <section class="panel stack files" aria-label=${title}>
        <h2>${title}</h2>
        ${names.length === 0 ? html`<p class="muted">Нет файлов</p>` : html`
          <ul class="list">${names.map((name) => html`<li class="stack">
            <span class="mono">${name}</span>
            <div class="actions">
              <button data-preview type="button" aria-label=${`Предпросмотр ${name}`} ?disabled=${!previewAvailable}
                @click=${() => this.showPreview(name, "proxy")}>Видео</button>
              <button type="button" aria-label=${`Миниатюра ${name}`} ?disabled=${!previewAvailable}
                @click=${() => this.showPreview(name, "thumbnail")}>Миниатюра</button>
              ${custom ? html`<button type="button" data-delete class="danger" aria-label=${`Удалить ${name}`}
                ?disabled=${!this.view?.snapshot?.device.connected || this.busy}
                @click=${() => {this.deleting = name; this.error = "";}}>Удалить</button>` : nothing}
            </div>
          </li>`)}</ul>`}
      </section>
    `;
  }

  private renderZone(items: string[], zone: number, names: readonly string[]) {
    return html`
      <fieldset data-zone=${zone + 1} class="panel stack" ?disabled=${this.busy}>
        <legend>Зона ${zone + 1}</legend>
        <label>Повтор
          <select ?disabled=${!items.length} name=${`playback-mode-${zone + 1}`}
            @change=${(event: Event) => this.edit(zone, {mode: (event.currentTarget as HTMLSelectElement).value})}>
            ${playbackModes.map((mode) => html`<option value=${mode} .selected=${live(this.draft!.playback_modes[zone] === mode)}>${mode}</option>`)}
          </select>
        </label>
        ${items.length ? html`<ol>${items.map((name, index) => html`<li>
          <div class="row">
            <span class="mono">${name}</span>
            <div class="actions">
              <button type="button" data-move-up ?disabled=${index === 0} aria-label=${`Выше ${name}`}
                @click=${() => this.edit(zone, {items: moveMedia(items, index, index - 1)})}>↑</button>
              <button type="button" data-move-down ?disabled=${index === items.length - 1} aria-label=${`Ниже ${name}`}
                @click=${() => this.edit(zone, {items: moveMedia(items, index, index + 1)})}>↓</button>
              <button type="button" aria-label=${`Убрать ${name} из плейлиста`}
                @click=${() => this.edit(zone, {items: items.filter((_, i) => i !== index)})}>Убрать</button>
            </div>
          </div>
        </li>`)}</ol>` : html`<p class="muted">Плейлист пуст</p>`}
        <label>Добавить файл
          <select ?disabled=${names.every((name) => items.includes(name))}
            @change=${(event: Event) => {
              const select = event.currentTarget as HTMLSelectElement;
              if (select.value) this.edit(zone, {items: [...items, select.value]});
              select.value = "";
            }}>
            <option value="">Выберите из медиатеки</option>
            ${names.filter((name) => !items.includes(name)).map((name) => html`<option value=${name}>${name}</option>`)}
          </select>
        </label>
      </fieldset>
    `;
  }
}
declare global { interface HTMLElementTagNameMap { "media-page": MediaPage; } }
