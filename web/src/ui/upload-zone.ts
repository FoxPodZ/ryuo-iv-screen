import {css, html, LitElement, nothing} from "lit";
import {customElement, property, state} from "lit/decorators.js";
import {uploadExtension} from "../media-model";
import type {AppStore, AppView} from "../store";
import {libraryStyles} from "./library-styles";

@customElement("upload-zone")
export class UploadZone extends LitElement {
  @property({attribute: false}) store?: AppStore;
  @property({attribute: false}) view?: Readonly<AppView>;
  @property({type: Boolean}) disabled = true;
  @state() private validation = "";

  static styles = [libraryStyles, css`
    .drop { padding: 1rem; border: 1px dashed #658084; border-radius: .8rem; background: #0e1b24; }
    progress { width: 100%; accent-color: #68e5d3; }
  `];

  private select(file?: File): void {
    if (!file || this.disabled || this.busy) return;
    if (!uploadExtension(file)) {
      this.validation = "Выберите файл MP4, GIF, PNG или JPG";
      return;
    }
    if (file.size === 0) {
      this.validation = "Файл пуст";
      return;
    }
    this.validation = "";
    void this.store?.uploadMedia(file);
  }

  private get busy(): boolean {
    return this.view?.upload?.phase === "uploading" || this.view?.upload?.phase === "processing";
  }

  protected render() {
    const upload = this.view?.upload;
    return html`
      <section class="panel stack" aria-labelledby="upload-heading">
        <h2 id="upload-heading">Загрузить файл</h2>
        <label class="drop" @dragover=${(event: DragEvent) => event.preventDefault()}
          @drop=${(event: DragEvent) => {
            event.preventDefault();
            this.select(event.dataTransfer?.files[0]);
          }}>
          Выберите или перетащите MP4, GIF, PNG или JPG
          <input type="file" accept=".mp4,.gif,.png,.jpg,.jpeg" ?disabled=${this.disabled || this.busy}
            @change=${(event: Event) => {
              const input = event.currentTarget as HTMLInputElement;
              this.select(input.files?.[0]);
              input.value = "";
            }}>
        </label>
        ${this.validation ? html`<p class="error" role="alert">${this.validation}</p>` : nothing}
        ${upload?.phase === "uploading" ? html`
          <div role="status">Передача файла на сервер${upload.percent === null ? "…" : ` · ${Math.round(upload.percent)}%`}</div>
          ${upload.percent === null
            ? html`<progress aria-label="Передача файла"></progress>`
            : html`<progress max="100" .value=${upload.percent} aria-label="Передача файла"></progress>`}
          <div><button type="button" data-cancel-upload @click=${() => this.store?.cancelUpload()}>Отменить передачу</button></div>
        ` : nothing}
        ${upload?.phase === "processing" ? html`
          <p role="status">Сервер обрабатывает файл. Отмена доступна только во время передачи.</p>
        ` : nothing}
        ${upload?.phase === "confirmed" ? html`<p class="active" role="status">Загрузка подтверждена · ${upload.name}</p>` : nothing}
        ${upload?.phase === "cancelled" ? html`<p role="status">Передача отменена</p>` : nothing}
        ${upload?.phase === "error" && !this.validation ? html`<p class="error" role="alert">${upload.message}</p>` : nothing}
      </section>
    `;
  }
}

declare global { interface HTMLElementTagNameMap { "upload-zone": UploadZone; } }
