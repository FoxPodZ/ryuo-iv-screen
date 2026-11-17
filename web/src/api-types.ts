export interface AuthStatus {
  required: boolean;
  authenticated: boolean;
  csrfToken: string | null;
  expiresIn?: number;
}

export interface SlotAssignment {
  enabled: boolean;
  measurement_id: string;
  widget: string;
  label: string | null;
}

export interface SensorRefDocument {
  provider: string;
  device: string;
  channel: string;
}

export interface SensorDescriptorDocument {
  ref: SensorRefDocument;
  measurementId: string;
  label: string;
  unit: string;
  available: boolean;
  source: string | null;
  metadata: Record<string, unknown>;
  error: string | null;
}

export interface SensorsResponse {
  sensors: SensorDescriptorDocument[];
  error: string | null;
}

export interface MutationResult {
  revision: number;
  saved: boolean;
  queued: boolean;
  applied: boolean;
  acked: boolean;
  error: string | null;
}

export interface ScreenMutationOutcome {
  ok: boolean;
  conflict: boolean;
  error: string | null;
}

export interface ScreenStateDocument {
  schema_version: number;
  revision: number;
  active_profile: string | null;
  screen_mode: string;
  media: string[][];
  playback_modes: string[];
  slots: SlotAssignment[];
  brightness: number;
  temperature_unit: "Celsius" | "Fahrenheit";
  refresh_interval: number;
  title_colors: string[];
  content_colors: string[];
  opacity: number;
  rgb_mode: string;
  rgb_target: string;
  thermal_source: string;
  sensor_selectors: Record<string, unknown>;
}

export interface DeviceDocument {
  connected: boolean;
  phase?: string;
  health: string;
  model?: string | null;
  firmware?: string | null;
  uptime?: number;
  sequence?: number;
  queue_depth?: number;
  reconnect_count?: number;
  recovery_count?: number;
  last_ack?: number | null;
  heartbeat_age?: number | null;
  last_error?: string | null;
  [key: string]: unknown;
}

export interface MeasurementDocument {
  value: number | null;
  unit: string;
  sampledAt: number;
  available: boolean;
  source?: string | null;
  error?: string | null;
  ref?: unknown;
}

export interface TelemetryDocument {
  sampledAt: number | null;
  measurements: Record<string, MeasurementDocument>;
  errors: Record<string, string>;
}

export interface SnapshotDocument {
  revision: number;
  state: ScreenStateDocument;
  device: DeviceDocument;
  telemetry: TelemetryDocument;
}

export interface StateResponse {
  revision: number;
  state: ScreenStateDocument;
}

export interface SseSnapshotEvent {
  id: number;
  snapshot: SnapshotDocument;
}

export interface DiagnosticsDocument {
  security: {
    bindMode: "loopback" | "lan";
    lanEnabled: boolean;
    authenticationRequired: boolean;
    trustedProxyCount: number;
    sessions: {active: number; capacity: number};
  };
  session: {required: boolean; authenticated: boolean; expiresIn?: number};
}
