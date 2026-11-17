import {html, LitElement, nothing} from "lit";
import {customElement, property, state} from "lit/decorators.js";
import {live} from "lit/directives/live.js";
import {profileExportUrl} from "../api";
import {
  configurationFromState, differsFromProfile, parseProfileImport, profileSlug, type ProfileDocument,
} from "../profile-model";
import type {AppStore, AppView} from "../store";
import {libraryStyles} from "./library-styles";

type Confirmation = {action: "delete"; profile: ProfileDocument} |
  {action: "apply"; profile: ProfileDocument; revision: number};
type NameEdit = {action: "rename" | "duplicate"; profile: ProfileDocument; name: string};

@customElement("profiles-page")
export class ProfilesPage extends LitElement {
  @property({attribute: false}) store?: AppStore;
  @property({attribute: false}) view?: Readonly<AppView>;
  @state() private name = "";
  @state() private edit: NameEdit | null = null;
  @state() private confirmation: Confirmation | null = null;
  @state() private busy = false;
  @state() private error = "";
  @state() private feedback = "";

  static styles = libraryStyles;

  get hasUnsavedChanges(): boolean {
    return Boolean(this.name.trim() || this.edit &&
      (this.edit.action === "duplicate" || this.edit.name.trim() !== this.edit.profile.name));
  }

  connectedCallback(): void {
    super.connectedCallback();
    void this.store?.loadProfiles();
  }

  private async run(action: () => Promise<void>, message: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    this.error = "";
    this.feedback = "";
    try {
      await action();
      this.feedback = message;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Операция с профилем не выполнена";
    } finally {
      this.busy = false;
    }
  }

  private create(event: SubmitEvent): void {
    event.preventDefault();
    const state = this.view?.snapshot?.state;
    const name = this.name.trim();
    if (!state || !name || !this.store) return;
    void this.run(async () => {
      await this.store!.writeProfile("create", {slug: profileSlug(name), name, ...configurationFromState(state)});
      this.name = "";
    }, "Профиль сохранён");
  }

  private saveName(event: SubmitEvent): void {
    event.preventDefault();
    const edit = this.edit;
    const name = edit?.name.trim();
    if (!edit || !name || !this.store) return;
    const document = edit.action === "duplicate" ? {name, slug: profileSlug(name)} : {name};
    void this.run(async () => {
      await this.store!.writeProfile(edit.action, document, edit.profile.slug);
      this.edit = null;
    }, edit.action === "duplicate" ? "Копия сохранена" : "Название сохранено");
  }

  private importFile(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || !this.store) return;
    void this.run(async () => {
      if (file.size > 1024 * 1024) throw new Error("JSON профиля превышает 1 МБ");
      await this.store!.writeProfile("import", parseProfileImport(await file.text()));
    }, "Профиль импортирован");
  }

  private apply(profile: ProfileDocument, revision = this.view?.snapshot?.revision): void {
    if (revision === undefined || !this.store) return;
    void this.run(async () => {
      const result = await this.store!.applyProfile(profile.slug, revision);
      if (!result.ok) throw new Error(result.error || "Сервер не подтвердил применение");
      this.confirmation = null;
    }, "Профиль сохранён и поставлен в очередь");
  }

  private saveCurrent(profile: ProfileDocument): void {
    const state = this.view?.snapshot?.state;
    if (!state || !this.store) return;
    void this.run(
      () => this.store!.writeProfile("update", configurationFromState(state), profile.slug),
      "Текущая конфигурация сохранена в профиль",
    );
  }

  private confirm(): void {
    const confirmation = this.confirmation;
    if (!confirmation || !this.store) return;
    if (confirmation.action === "apply") {
      this.apply(confirmation.profile, confirmation.revision);
      return;
    }
    void this.run(async () => {
      await this.store!.deleteProfile(confirmation.profile.slug);
      this.confirmation = null;
    }, "Профиль удалён");
  }

  protected render() {
    const profiles = this.view?.profiles;
    const activeSlug = this.view?.snapshot?.state.active_profile;
    const active = profiles?.find((profile) => profile.slug === activeSlug);
    const snapshotState = this.view?.snapshot?.state;
    const modified = Boolean(active && snapshotState && differsFromProfile(snapshotState, active));
    const factory = profiles?.filter((profile) => profile.factory) ?? [];
    const custom = profiles?.filter((profile) => !profile.factory) ?? [];
    const confirmation = this.confirmation;
    return html`
      <section class="page" aria-labelledby="profiles-heading">
        <h1 id="profiles-heading">Профили</h1>
        ${modified ? html`<p class="notice" role="status">Есть несохранённые в активном профиле изменения экрана.</p>` : nothing}
        ${this.hasUnsavedChanges ? html`<p class="notice" role="status">Есть несохранённые изменения профиля.</p>` : nothing}
        ${this.view?.profilesError || this.error ? html`<p class="error" role="alert">${this.error || this.view?.profilesError}</p>` : nothing}
        ${this.feedback ? html`<p role="status" class="active">${this.feedback}</p>` : nothing}
        <div class="columns">
          <form class="panel stack" @submit=${this.create}>
            <h2>Создать из настроек экрана</h2>
            <label>Название профиля
              <input name="profile-name" required maxlength="100" .value=${live(this.name)}
                @input=${(event: Event) => {this.name = (event.currentTarget as HTMLInputElement).value;}}>
            </label>
            <div><button class="primary" data-create type="submit"
              ?disabled=${!snapshotState || !this.name.trim() || this.busy}>Создать профиль</button></div>
          </form>
          <section class="panel stack">
            <h2>Импортировать профиль</h2>
            <label>Файл JSON
              <input name="profile-import" type="file" accept=".json,application/json" ?disabled=${this.busy} @change=${this.importFile}>
            </label>
          </section>
        </div>
        ${this.edit ? html`
          <form class="panel stack" @submit=${this.saveName} aria-labelledby="edit-profile-title">
            <h2 id="edit-profile-title">${this.edit.action === "rename" ? "Переименовать" : "Дублировать"} · ${this.edit.profile.name}</h2>
            <label>Название
              <input name="edit-profile-name" required maxlength="100" .value=${live(this.edit.name)} @input=${(event: Event) => {
                if (this.edit) this.edit = {...this.edit, name: (event.currentTarget as HTMLInputElement).value};
              }}>
            </label>
            <div class="actions">
              <button type="submit" class="primary" data-save-name ?disabled=${!this.edit.name.trim() || this.busy}>Сохранить</button>
              <button type="button" ?disabled=${this.busy} @click=${() => {this.edit = null;}}>Отмена</button>
            </div>
          </form>` : nothing}
        ${confirmation ? html`
          <section role="alertdialog" class="panel stack" aria-labelledby="profile-confirm-title" aria-describedby="profile-confirm-description">
            <h2 id="profile-confirm-title">${confirmation.action === "delete" ? "Удалить профиль?" : "Применить другой профиль?"}</h2>
            <p id="profile-confirm-description">${confirmation.profile.name}</p>
            ${confirmation.action === "apply" ? html`<p class="notice">Текущая конфигурация не сохранена в активном профиле. Применение заменит её.</p>`
              : activeSlug === confirmation.profile.slug ? html`<p class="notice">Экран продолжит использовать текущие настройки после удаления профиля.</p>` : nothing}
            <div class="actions">
              <button type="button" ?disabled=${this.busy} @click=${() => {this.confirmation = null;}}>Отмена</button>
              <button type="button" data-confirm-delete ?disabled=${this.busy} @click=${this.confirm}>
                ${confirmation.action === "delete" ? "Удалить" : "Применить"}
              </button>
            </div>
          </section>` : nothing}
        ${!profiles ? html`
          <p role="status">${this.view?.profilesError ? "Список профилей недоступен" : "Загрузка профилей…"}</p>
          ${this.view?.profilesError ? html`<div><button type="button" @click=${() => this.store?.loadProfiles()}>Повторить</button></div>` : nothing}
        ` : html`<div class="columns">
          ${this.renderList("Встроенные Miku", factory, activeSlug, modified)}
          ${this.renderList("Пользовательские профили", custom, activeSlug, modified)}
        </div>`}
      </section>
    `;
  }

  private renderList(title: string, profiles: ProfileDocument[], active: string | null | undefined, modified: boolean) {
    return html`
      <section class="panel stack" aria-label=${title}>
        <h2>${title}</h2>
        ${profiles.length === 0 ? html`<p class="muted">Нет профилей</p>` : html`
          <ul class="list">${profiles.map((profile) => html`
            <li class="stack" data-profile=${profile.slug}>
              <div class="row">
                <h3>${profile.name}</h3>
                ${active === profile.slug ? html`<span class="active" aria-current="true">Активный</span>` : nothing}
              </div>
              <p class="muted">${profile.screen_mode} · ${profile.media.flat().length} медиа</p>
              <div class="actions">
                <button type="button" data-apply ?disabled=${this.busy || !this.view?.snapshot}
                  @click=${() => {
                    const revision = this.view?.snapshot?.revision;
                    if (revision === undefined) return;
                    if (modified) this.confirmation = {action: "apply", profile, revision};
                    else this.apply(profile, revision);
                  }}>Применить</button>
                <button type="button" data-duplicate ?disabled=${this.busy} @click=${() => {
                  this.edit = {action: "duplicate", profile, name: `${profile.name} (копия)`};
                }}>Дублировать</button>
                <a class="button" data-export href=${profileExportUrl(profile.slug)} download=${`${profile.slug}.json`}>Экспорт</a>
                ${!profile.factory ? html`
                  <button type="button" data-rename ?disabled=${this.busy}
                    @click=${() => {this.edit = {action: "rename", profile, name: profile.name};}}>Переименовать</button>
                  ${active === profile.slug && modified ? html`<button type="button" ?disabled=${this.busy}
                    @click=${() => this.saveCurrent(profile)}>Сохранить настройки экрана</button>` : nothing}
                  <button type="button" class="danger" data-delete ?disabled=${this.busy}
                    @click=${() => {this.confirmation = {action: "delete", profile};}}>Удалить</button>
                ` : nothing}
              </div>
            </li>
          `)}</ul>`}
      </section>`;
  }
}
declare global { interface HTMLElementTagNameMap { "profiles-page": ProfilesPage; } }
