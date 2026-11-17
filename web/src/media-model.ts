import type {ScreenStateDocument} from "./api-types";

export interface MediaCatalog {
  factory: string[];
  custom: string[];
  tools: {ffmpeg: boolean; ffprobe: boolean};
  adb: {available: boolean; reason: string | null};
}

export interface MediaResult {
  jobId: string;
  name: string | null;
  applied: boolean;
  confirmed: boolean;
  error: string | null;
}

export type UploadStatus =
  | {phase: "idle" | "processing" | "cancelled"}
  | {phase: "uploading"; percent: number | null}
  | {phase: "confirmed"; name: string}
  | {phase: "error"; message: string};

export const playbackModes = ["Single", "Random", "Cycle"] as const;

export interface Playlist {
  media: string[][];
  playback_modes: string[];
}

export const playlistFromState = (state: ScreenStateDocument): Playlist => ({
  media: state.media.map((items) => [...items]),
  playback_modes: [...state.playback_modes],
});

export function moveMedia(items: readonly string[], from: number, to: number): string[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export const uploadExtension = (file: File): string | null =>
  /\.(mp4|gif|png|jpe?g)$/i.exec(file.name)?.[1].toLowerCase() ?? null;
