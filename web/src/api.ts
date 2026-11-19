import type {
  AuthStatus,
  DeviceDocument,
  DiagnosticsDocument,
  MutationResult,
  SensorsResponse,
  SnapshotDocument,
  StateResponse,
  TelemetryDocument,
} from "./api-types";
import type {EventConnection, EventConnector} from "./store";
import {uploadExtension, type MediaCatalog, type MediaResult} from "./media-model";
import type {ProfileDocument} from "./profile-model";

const API = "/api/v1";

export const mediaPreviewUrl = (kind: "thumbnail" | "proxy", name: string): string =>
  `${API}/media/preview/${kind}/${encodeURIComponent(name)}`;

const profilePath = (slug: string): string => `/profiles/${encodeURIComponent(slug)}`;

export const profileExportUrl = (slug: string): string => `${API}${profilePath(slug)}/export`;

export interface MediaTransfer {
  result: Promise<MediaResult>;
  cancel(): void;
}

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
      : "confirmed" in body && typeof body.error === "string"
        ? body.error : `HTTP ${response.status}`;
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

  async loadMedia(): Promise<MediaCatalog> {
    const {factory, custom, tools, adb} = await this.request<MediaCatalog>("/media");
    return {factory, custom, tools, adb: {available: adb.available, reason: adb.reason, targetToken: adb.targetToken}};
  }

  async deleteMedia(name: string): Promise<MediaResult> {
    return this.request<MediaResult>(`/media/${encodeURIComponent(name)}`, {method: "DELETE"});
  }

  uploadMedia(
    file: File,
    onProgress: (percent: number | null) => void,
    onProcessing: () => void,
    targetToken?: string,
  ): MediaTransfer {
    const extension = uploadExtension(file);
    if (!extension) throw new Error("Выберите файл MP4, GIF, PNG или JPG");
    const request = new XMLHttpRequest();
    request.open("POST", `${API}/media/upload`);
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.setRequestHeader("Accept", "application/json");
    request.setRequestHeader("X-Filename", `upload.${extension}`);
    if (targetToken) request.setRequestHeader("X-Ryuo-Media-Target", targetToken);
    if (this.csrfToken) request.setRequestHeader("X-CSRF-Token", this.csrfToken);

    let transmitting = true;
    const result = new Promise<MediaResult>((resolve, reject) => {
      request.upload.addEventListener("progress", (event) => {
        if (transmitting) onProgress(event.lengthComputable && event.total > 0
          ? 100 * event.loaded / event.total : null);
      });
      request.upload.addEventListener("load", () => {
        transmitting = false;
        onProcessing();
      });
      request.addEventListener("load", () => {
        transmitting = false;
        let document: Partial<MediaResult> & {message?: string} = {};
        try {
          document = JSON.parse(request.responseText) ?? {};
        } catch {
          // A proxy can return a non-JSON error page.
        }
        if (request.status >= 200 && request.status < 300 && document.confirmed === true &&
            typeof document.name === "string" && document.name.length > 0) {
          resolve(document as MediaResult);
        } else {
          reject(new ApiError(request.status, "upload_failed", document.message ||
            document.error || `Сервер не подтвердил загрузку (HTTP ${request.status})`));
        }
      });
      request.addEventListener("error", () => reject(new Error("Связь с сервером прервалась")));
      request.addEventListener("abort", () => reject(new DOMException("Передача отменена", "AbortError")));
      request.send(file);
    });
    return {result, cancel: () => { if (transmitting) request.abort(); }};
  }

  async loadDiagnostics(): Promise<DiagnosticsDocument> {
    return this.request<DiagnosticsDocument>("/diagnostics");
  }

  async loadProfiles(): Promise<ProfileDocument[]> {
    return (await this.request<{profiles: ProfileDocument[]}>("/profiles")).profiles;
  }

  async writeProfile(
    path: "create" | "import" | "rename" | "duplicate" | "update",
    document: Record<string, unknown>,
    slug = "",
  ): Promise<ProfileDocument> {
    const endpoint = {
      create: "/profiles", import: "/profiles/import", rename: profilePath(slug),
      update: profilePath(slug), duplicate: `${profilePath(slug)}/duplicate`,
    }[path];
    return (await this.request<{profile: ProfileDocument}>(endpoint, {
      method: path === "rename" || path === "update" ? "PATCH" : "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(document),
    })).profile;
  }

  async deleteProfile(slug: string): Promise<void> {
    await this.request(profilePath(slug), {method: "DELETE"});
  }

  async applyProfile(slug: string, revision: number): Promise<MutationResult> {
    return this.request<MutationResult>(`${profilePath(slug)}/apply`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "If-Match": String(revision)},
      body: JSON.stringify({revision}),
    });
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
