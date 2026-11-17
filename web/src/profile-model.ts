import type {ScreenStateDocument} from "./api-types";

export type ProfileConfiguration = Omit<ScreenStateDocument, "revision" | "active_profile">;

export interface ProfileDocument extends ProfileConfiguration {
  slug: string;
  name: string;
  factory: boolean;
}

export function configurationFromState(state: ScreenStateDocument): ProfileConfiguration {
  const {revision: _revision, active_profile: _activeProfile, ...configuration} = state;
  return configuration;
}

export function profileSlug(name: string): string {
  const readable = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  if (readable) return readable;
  const random = crypto.getRandomValues(new Uint8Array(8));
  return "profile-" + Array.from(random, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function profileCopySlug(sourceSlug: string, profiles: readonly ProfileDocument[]): string {
  const taken = new Set(profiles.map(({slug}) => slug));
  const base = `${sourceSlug}-copy`;
  let candidate = base;
  for (let suffix = 2; taken.has(candidate); suffix += 1) {
    candidate = `${base}-${suffix}`;
  }
  return candidate;
}

export function parseProfileImport(text: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("Файл не содержит корректный JSON");
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("JSON профиля должен содержать объект");
  }
  return parsed as Record<string, unknown>;
}

function sortedKeys(_key: string, value: unknown): unknown {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return value;
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)));
}

export function differsFromProfile(state: ScreenStateDocument, profile: ProfileDocument): boolean {
  const {slug: _slug, name: _name, factory: _factory, ...configuration} = profile;
  return JSON.stringify(configurationFromState(state), sortedKeys) !== JSON.stringify(configuration, sortedKeys);
}
