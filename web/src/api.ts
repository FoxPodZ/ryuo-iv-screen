import type {
  AuthStatus,
  DeviceDocument,
  MutationResult,
  SensorsResponse,
  SnapshotDocument,
  StateResponse,
  TelemetryDocument,
} from "./api-types";
import type {EventConnection, EventConnector} from "./store";

const API = "/api/v1";

export type ScreenPatchKind = "brightness" | "screen" | "telemetry-settings";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function readJson<T>(response: Response): Promise<T> {
  let body: Record<string, unknown> = {};
  try {
    body = await response.json() as Record<string, unknown>;
  } catch {
    // A status and human-readable fallback are still useful for proxy failures.
  }
  if (!response.ok) {
    const code = typeof body.error === "string" ? body.error : "http_error";
    const message = typeof body.message === "string"
      ? body.message
      : `HTTP ${response.status}`;
    throw new ApiError(response.status, code, message);
  }
  return body as T;
}

export class ApiClient {
  private csrfToken: string | null = null;

  setCsrfToken(value: string | null): void {
    this.csrfToken = value;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (this.csrfToken && init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase())) {
      headers.set("X-CSRF-Token", this.csrfToken);
    }
    return readJson<T>(await fetch(`${API}${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
    }));
  }

  async authStatus(): Promise<AuthStatus> {
    const status = await this.request<AuthStatus>("/auth/status");
    this.setCsrfToken(status.csrfToken);
    return status;
  }

  async login(password: string): Promise<AuthStatus> {
    const status = await this.request<AuthStatus>("/auth/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({password}),
    });
    this.setCsrfToken(status.csrfToken);
    return status;
  }

  async loadSnapshot(): Promise<SnapshotDocument> {
    const [state, telemetry, device] = await Promise.all([
      this.request<StateResponse>("/state"),
      this.request<TelemetryDocument>("/telemetry"),
      this.request<DeviceDocument>("/device"),
    ]);
    return {
      revision: state.revision,
      state: state.state,
      telemetry,
      device,
    };
  }

  async loadSensors(): Promise<SensorsResponse> {
    return this.request<SensorsResponse>("/sensors");
  }

  async patchState(
    kind: ScreenPatchKind,
    revision: number,
    changes: Record<string, unknown>,
  ): Promise<MutationResult> {
    return this.request<MutationResult>(`/${kind}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "If-Match": String(revision),
      },
      body: JSON.stringify({revision, ...changes}),
    });
  }
}

function parseEventBlock(block: string): {id: number; snapshot: SnapshotDocument} | null {
  let id: number | null = null;
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("id:")) {
      const parsed = Number.parseInt(line.slice(3).trim(), 10);
      if (Number.isSafeInteger(parsed) && parsed >= 0) id = parsed;
    } else if (line.startsWith("data:")) {
      data.push(line.slice(5).trimStart());
    }
  }
  if (id === null || data.length === 0) return null;
  const snapshot = JSON.parse(data.join("\n")) as SnapshotDocument;
  return {id, snapshot};
}

export class EventStream implements EventConnector {
  connect(
    lastEventId: number | null,
    onEvent: (id: number, value: SnapshotDocument) => void,
    onError: (error: unknown) => void,
  ): EventConnection {
    const controller = new AbortController();
    void this.pump(controller, lastEventId, onEvent).catch((error: unknown) => {
      if (!controller.signal.aborted) onError(error);
    });
    return {close: () => controller.abort()};
  }

  private async pump(
    controller: AbortController,
    lastEventId: number | null,
    onEvent: (id: number, value: SnapshotDocument) => void,
  ): Promise<void> {
    const headers = new Headers({Accept: "text/event-stream"});
    if (lastEventId !== null) headers.set("Last-Event-ID", String(lastEventId));
    const response = await fetch(`${API}/events`, {
      credentials: "same-origin",
      headers,
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      await readJson<never>(response);
      return;
    }
    if (!response.body) throw new Error("Сервер не открыл поток событий");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!controller.signal.aborted) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true}).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const event = parseEventBlock(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (event) onEvent(event.id, event.snapshot);
        boundary = buffer.indexOf("\n\n");
      }
    }
    if (!controller.signal.aborted) throw new Error("Поток событий закрыт сервером");
  }
}
