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
