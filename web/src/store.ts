import {ApiError, type ApiClient, type MediaTransfer, type ScreenPatchKind} from "./api";
import type {
  AuthStatus,
  DiagnosticsDocument,
  MutationResult,
  SensorDescriptorDocument,
  SensorsResponse,
  ScreenMutationOutcome,
  SnapshotDocument,
} from "./api-types";
import type {MediaCatalog, UploadStatus} from "./media-model";
import type {ProfileDocument} from "./profile-model";

export type AppPhase = "loading" | "ready" | "login" | "error";

export interface AppView {
  phase: AppPhase;
  auth: AuthStatus | null;
  csrfToken: string | null;
  snapshot: SnapshotDocument | null;
  error: string | null;
  connected: boolean;
  lastEventId: number;
  retryDelay: number;
  sensors?: readonly SensorDescriptorDocument[];
  mutationError?: string | null;
  media?: MediaCatalog;
  profiles?: readonly ProfileDocument[];
  diagnostics?: DiagnosticsDocument;
  upload?: UploadStatus;
  mediaError?: string | null;
  profilesError?: string | null;
  diagnosticsError?: string | null;
}

type LibraryApi = Pick<ApiClient,
  "loadMedia" | "deleteMedia" | "uploadMedia" | "loadProfiles" | "writeProfile" |
  "deleteProfile" | "applyProfile" | "loadDiagnostics">;

export interface ApiGateway extends Partial<LibraryApi> {
  authStatus(): Promise<AuthStatus>;
  loadSnapshot(): Promise<SnapshotDocument>;
  login(password: string): Promise<AuthStatus>;
  setCsrfToken?(value: string | null): void;
  loadSensors?(): Promise<SensorsResponse>;
  patchState?(
    kind: ScreenPatchKind,
    revision: number,
    changes: Record<string, unknown>,
  ): Promise<MutationResult>;
}

export interface EventConnection { close(): void; }

export interface EventConnector {
  connect(
    lastEventId: number | null,
    onEvent: (id: number, value: SnapshotDocument) => void,
    onError: (error: unknown) => void,
  ): EventConnection;
}

type Listener = (value: Readonly<AppView>) => void;
type Scheduler = (run: () => void, delay: number) => unknown;
type ScheduleCanceller = (handle: unknown) => void;

const deepFreeze = <T>(value: T): T => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const nested of Object.values(value as Record<string, unknown>)) deepFreeze(nested);
    Object.freeze(value);
  }
  return value;
};

const initialView = (): AppView => ({
  phase: "loading",
  auth: null,
  csrfToken: null,
  snapshot: null,
  error: null,
  connected: false,
  lastEventId: 0,
  retryDelay: 500,
  sensors: [],
  mutationError: null,
});

const errorMessage = (error: unknown): string => error instanceof Error
  ? error.message
  : "Неизвестная ошибка";

export class AppStore {
  private state: Readonly<AppView> = deepFreeze(initialView());
  private readonly listeners = new Set<Listener>();
  private connection: EventConnection | null = null;
  private retryToken = 0;
  private stopped = false;
  private sessionTimer: unknown | null = null;
  private sessionGeneration = 0;
  private transfer: MediaTransfer | null = null;
  private resourceRequests = {media: 0, profiles: 0, diagnostics: 0};

  constructor(
    private readonly api: ApiGateway,
    private readonly events: EventConnector,
    private readonly schedule: Scheduler = (run, delay) => window.setTimeout(run, delay),
    private readonly cancelSchedule: ScheduleCanceller = (handle) => window.clearTimeout(handle as number),
  ) {}

  get value(): Readonly<AppView> { return this.state; }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  private update(change: Partial<AppView>): void {
    this.state = deepFreeze({...this.state, ...change});
    for (const listener of this.listeners) listener(this.state);
  }

  async start(): Promise<void> {
    this.stopped = false;
    this.clearSessionExpiry();
    this.connection?.close();
    this.connection = null;
    this.resetLibrary();
    this.update({phase: "loading", error: null, connected: false});
    try {
      const auth = await this.api.authStatus();
      const authActive = this.applyAuth(auth);
      if (auth.required && !auth.authenticated) {
        this.update({phase: "login"});
        return;
      }
      if (!authActive) return;
      await this.loadAndConnect(this.sessionGeneration);
    } catch (error) {
      this.handleLoadError(error);
    }
  }

  stop(): void {
    this.stopped = true;
    this.resetLibrary();
    this.retryToken += 1;
    this.clearSessionExpiry();
    this.connection?.close();
    this.connection = null;
    this.update({connected: false});
  }

  async login(password: string): Promise<void> {
    this.update({error: null});
    try {
      const auth = await this.api.login(password);
      if (!this.applyAuth(auth)) return;
      this.update({phase: "loading"});
      await this.loadAndConnect(this.sessionGeneration);
    } catch (error) {
      this.handleLoadError(error, true);
    }
  }

  async ensureSensors(force = false): Promise<void> {
    if ((!force && (this.state.sensors?.length ?? 0) > 0) || !this.api.loadSensors) return;
    const generation = this.sessionGeneration;
    try {
      const response = await this.api.loadSensors();
      if (!this.stopped && generation === this.sessionGeneration) {
        this.update({sensors: response.sensors, mutationError: response.error});
      }
    } catch (error) {
      if (!this.stopped && generation === this.sessionGeneration) {
        this.update({mutationError: `Не удалось загрузить датчики: ${errorMessage(error)}`});
      }
    }
  }

  async loadMedia(): Promise<void> {
    await this.loadLibrary("media", () => this.api.loadMedia?.());
  }

  async loadProfiles(): Promise<void> {
    await this.loadLibrary("profiles", () => this.api.loadProfiles?.());
  }

  async loadDiagnostics(): Promise<void> {
    await this.loadLibrary("diagnostics", () => this.api.loadDiagnostics?.());
  }

  private async loadLibrary<K extends "media" | "profiles" | "diagnostics">(
    key: K, load: () => Promise<AppView[K]> | undefined,
  ): Promise<void> {
    const generation = this.sessionGeneration;
    const request = ++this.resourceRequests[key];
    const errorKey = `${key}Error` as const;
    const isCurrent = () => !this.stopped && generation === this.sessionGeneration &&
      request === this.resourceRequests[key];
    try {
      const value = await load();
      if (isCurrent()) this.update({[key]: value, [errorKey]: null});
    } catch (error) {
      if (!isCurrent()) return;
      if (error instanceof ApiError && error.status === 401) this.handleLoadError(error);
      else this.update({[errorKey]: errorMessage(error)});
    }
  }

  async deleteMedia(name: string): Promise<void> {
    if (!this.api.deleteMedia || !this.state.media?.custom.includes(name) ||
        this.state.media.factory.includes(name)) throw new Error("Можно удалить только пользовательский файл");
    const result = await this.api.deleteMedia(name);
    if (result.confirmed !== true) throw new Error(result.error || "Сервер не подтвердил удаление");
    await this.loadMedia();
  }

  async uploadMedia(file: File): Promise<void> {
    if (!this.api.uploadMedia || !this.state.media?.adb.available || this.transfer) return;
    const generation = this.sessionGeneration;
    const current = () => !this.stopped && generation === this.sessionGeneration;
    this.update({upload: {phase: "uploading", percent: null}});
    try {
      this.transfer = this.api.uploadMedia(file, (percent) => {
        if (current()) this.update({upload: {phase: "uploading", percent}});
      }, () => {
        if (current()) this.update({upload: {phase: "processing"}});
      }, this.state.media.adb.targetToken);
      const result = await this.transfer.result;
      if (!current()) return;
      if (result.confirmed !== true || !result.name) throw new Error("Сервер не подтвердил загрузку");
      this.update({upload: {phase: "confirmed", name: result.name}});
      void this.loadMedia();
    } catch (error) {
      if (!current()) return;
      if (error instanceof ApiError && error.status === 401) this.handleLoadError(error);
      else this.update({upload: error instanceof DOMException && error.name === "AbortError"
        ? {phase: "cancelled"} : {phase: "error", message: errorMessage(error)}});
    } finally {
      if (current()) this.transfer = null;
    }
  }

  cancelUpload(): void {
    if (this.state.upload?.phase === "uploading") this.transfer?.cancel();
  }

  async writeProfile(
    action: Parameters<LibraryApi["writeProfile"]>[0],
    document: Record<string, unknown>, slug?: string,
  ): Promise<void> {
    if (!this.api.writeProfile) throw new Error("API профилей недоступен");
    await this.api.writeProfile(action, document, slug);
    await this.loadProfiles();
  }

  async deleteProfile(slug: string): Promise<void> {
    if (!this.api.deleteProfile) throw new Error("API профилей недоступен");
    await this.api.deleteProfile(slug);
    await this.loadProfiles();
  }

  async applyProfile(slug: string, revision: number): Promise<ScreenMutationOutcome> {
    return this.mutateState(() => this.api.applyProfile?.(slug, revision));
  }

  async patchScreen(
    kind: ScreenPatchKind,
    changes: Record<string, unknown>,
    revision = this.state.snapshot?.revision,
  ): Promise<ScreenMutationOutcome> {
    return this.mutateState(() => revision === undefined
      ? undefined : this.api.patchState?.(kind, revision, changes));
  }

  private async mutateState(
    send: () => Promise<MutationResult> | undefined,
  ): Promise<ScreenMutationOutcome> {
    const generation = this.sessionGeneration;
    const current = () => !this.stopped && generation === this.sessionGeneration;
    const updateSnapshot = (snapshot: SnapshotDocument | null) => {
      const existing = this.state.snapshot;
      return existing && (!snapshot || existing.revision > snapshot.revision) ? existing : snapshot;
    };
    try {
      const result = await send();
      if (!result) throw new Error("Редактор ещё не получил текущее состояние");
      const loaded = await this.api.loadSnapshot();
      if (!current()) return {ok: false, conflict: false, error: null};
      const snapshot = updateSnapshot(loaded);
      if (!result.saved || !result.queued || result.error) {
        const error = result.error || "Состояние сохранено, но команда не поставлена в очередь";
        this.update({snapshot, mutationError: error});
        return {ok: false, conflict: false, error};
      }
      this.update({snapshot, mutationError: null, error: null});
      return {ok: true, conflict: false, error: null};
    } catch (error) {
      if (!current()) return {ok: false, conflict: false, error: null};
      if (error instanceof ApiError && error.status === 401) this.handleLoadError(error);
      if (error instanceof ApiError && error.status === 409) {
        let snapshot = this.state.snapshot;
        let refreshed = false;
        try {
          snapshot = await this.api.loadSnapshot();
          refreshed = true;
        } catch {
          // Preserve the last good state while still reporting the conflict.
        }
        const message = refreshed ? "Конфликт ревизий: загружено актуальное состояние"
          : "Конфликт ревизий: не удалось загрузить актуальное состояние";
        if (current()) this.update({snapshot: updateSnapshot(snapshot), mutationError: message});
        return {ok: false, conflict: true, error: message};
      }
      const message = `Изменение не применено: ${errorMessage(error)}`;
      this.update({mutationError: message});
      return {ok: false, conflict: false, error: message};
    }
  }

  private resetLibrary(): void {
    this.cancelUpload();
    this.transfer = null;
    this.update({media: undefined, profiles: undefined, diagnostics: undefined, upload: undefined,
      mediaError: null, profilesError: null, diagnosticsError: null, sensors: []});
  }

  private async loadAndConnect(generation: number): Promise<void> {
    const snapshot = await this.api.loadSnapshot();
    if (this.stopped || generation !== this.sessionGeneration) return;
    this.update({phase: "ready", snapshot, error: null});
    this.openEvents();
  }

  private handleLoadError(error: unknown, loginAttempt = false): void {
    if (error instanceof ApiError && error.status === 401) {
      this.clearSessionExpiry();
      this.api.setCsrfToken?.(null);
      this.resetLibrary();
      this.connection?.close();
      this.connection = null;
      this.update({
        phase: "login",
        connected: false,
        error: errorMessage(error),
        auth: {required: true, authenticated: false, csrfToken: null},
        csrfToken: null,
      });
      return;
    }
    this.update({
      phase: loginAttempt ? "login" : "error",
      connected: false,
      error: errorMessage(error),
    });
  }

  private applyAuth(auth: AuthStatus): boolean {
    this.clearSessionExpiry();
    this.api.setCsrfToken?.(auth.csrfToken);
    this.update({auth, csrfToken: auth.csrfToken});
    if (!auth.required || !auth.authenticated) return true;
    const seconds = auth.expiresIn;
    if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) {
      this.expireSession(this.sessionGeneration);
      return false;
    }
    const generation = this.sessionGeneration;
    this.sessionTimer = this.schedule(
      () => this.expireSession(generation),
      seconds * 1000,
    );
    return true;
  }

  private clearSessionExpiry(): void {
    this.sessionGeneration += 1;
    if (this.sessionTimer !== null) this.cancelSchedule(this.sessionTimer);
    this.sessionTimer = null;
  }

  private expireSession(generation: number): void {
    if (this.stopped || generation !== this.sessionGeneration) return;
    this.sessionGeneration += 1;
    this.sessionTimer = null;
    this.retryToken += 1;
    this.connection?.close();
    this.connection = null;
    this.api.setCsrfToken?.(null);
    this.resetLibrary();
    this.update({
      phase: "login",
      auth: {required: true, authenticated: false, csrfToken: null, expiresIn: 0},
      csrfToken: null,
      connected: false,
      error: "Сессия истекла. Войдите снова.",
    });
  }

  private openEvents(): void {
    if (this.stopped) return;
    this.connection?.close();
    const lastId = this.state.lastEventId > 0 ? this.state.lastEventId : null;
    this.connection = this.events.connect(
      lastId,
      (id, snapshot) => this.acceptEvent(id, snapshot),
      (error) => this.handleEventError(error),
    );
  }

  private acceptEvent(id: number, snapshot: SnapshotDocument): void {
    if (!Number.isSafeInteger(id) || id <= this.state.lastEventId) return;
    if (this.state.snapshot && snapshot.revision < this.state.snapshot.revision) return;
    this.update({
      phase: "ready",
      snapshot,
      error: null,
      connected: true,
      lastEventId: id,
      retryDelay: 500,
    });
  }

  private handleEventError(error: unknown): void {
    this.connection?.close();
    this.connection = null;
    if (error instanceof ApiError && error.status === 401) {
      this.handleLoadError(error);
      return;
    }
    const delay = this.state.retryDelay;
    this.update({connected: false, error: errorMessage(error), retryDelay: Math.min(delay * 2, 10_000)});
    const token = ++this.retryToken;
    this.schedule(() => {
      if (!this.stopped && token === this.retryToken) this.openEvents();
    }, delay);
  }
}

export const createDefaultStore = (api: ApiClient, events: EventConnector): AppStore => new AppStore(api, events);
