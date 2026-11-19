<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Use the Web UI

Open [the local control panel](http://127.0.0.1:8746/) after starting `ryuo-screen.service`. For remote access use the hostname of your configured TLS proxy. If a login expires, sign in again. The Web UI and CLI share the daemon's saved state.

| Page | What to do |
| --- | --- |
| Dashboard | Check device health, firmware, last heartbeat and live readings before diagnosing an empty panel. Watch timestamps and unavailable readings after reconnect. |
| Экран (Screen) | Choose full or split layout, assign the six slots, then edit colors, brightness, opacity and RGB/thermal effects. Split uses three slots per zone. The browser preview approximates geometry and labels. Verify rendering and playback on the physical cooler. |
| Медиатека (Media) | Inspect the factory/custom lists from the device, browse previews or upload MP4, GIF, PNG or JPEG. ADB delivers files. FFmpeg/ffprobe inspect and convert formats. Wait for device confirmation and check the refreshed list before repeating a failed upload. Only custom items can be deleted. |
| Профили (Profiles) | Apply a saved configuration, duplicate an example, rename a custom profile, or export/import JSON. Applying an example references media already present on the cooler. |
| Настройки (Settings) | Select the GPU or motherboard channel by stable identity, change units and refresh timing, inspect access/session status and copy sanitized diagnostics. |

Four Miku Single profiles reference `Ryuo_IV_MIKU_WW_01.mp4` through `Ryuo_IV_MIKU_WW_04.mp4`. Miku Cycle references all four in order. Compare their exact case-sensitive names with Media on your firmware. When media is unresolved, duplicate the profile and select available files. The project distributes the profile definitions only.

The page receives live snapshots over SSE. After a stale edit, reload the current state and review the changed fields before applying again. “Saved” means the daemon wrote the desired state. Queuing, hardware application and acknowledgement are separate stages. [API reference](api.md) · [Telemetry and selectors](telemetry.md)
