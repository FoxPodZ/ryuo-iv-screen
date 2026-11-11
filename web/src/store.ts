import {ApiError, type ApiClient} from "./api";
import type {AuthStatus, SnapshotDocument} from "./api-types";

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
}

export interface ApiGateway {
  authStatus(): Promise<AuthStatus>;
  loadSnapshot(): Promise<SnapshotDocument>;
  login(password: string): Promise<AuthStatus>;
  setCsrfToken?(value: string | null): void;
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

  private async loadAndConnect(generation: number): Promise<void> {
    const snapshot = await this.api.loadSnapshot();
    if (this.stopped || generation !== this.sessionGeneration) return;
    this.update({phase: "ready", snapshot, error: null});
    this.openEvents();
  }

  private handleLoadError(error: unknown, loginAttempt = false): void {
    if (error instanceof ApiError && error.status === 401) {
      this.clearSessionExpiry();
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
