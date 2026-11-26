<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# HTTP API v1

The browser uses `http://127.0.0.1:8746`. Local clients can send the same HTTP requests through `/run/ryuo-screen/control.sock`. JSON is UTF-8. Send `Content-Type: application/json` for POST and PATCH, except for the binary upload. URL-encode path parameters. See the [authentication and proxy guide](security.md).

## Read state and watch changes

| Request | Response |
| --- | --- |
| `GET /api/v1/state` | `{revision, state}`. The state is the persisted desired configuration. |
| `GET /api/v1/device` | `phase`, `health`, `connected`, `model`, `firmware`, `descriptor` (serials redacted), `sequence`, `queue_depth`, `reconnect_count`, `recovery_count`, `last_ack`, `heartbeat_age`, `last_error`, `uptime`. Times are seconds. |
| `GET /api/v1/sensors` | `{sensors, error}`. Each entry has `ref`, `measurementId`, `label`, `unit`, `source`, `metadata`, `available` and `error`. |
| `GET /api/v1/telemetry` | `{sampledAt, measurements, errors}`. Measurements are keyed by logical ID and carry `ref`, `value`, `unit`, `source`, `available`, `sampledAt` and `error`. Timestamps are Unix seconds. Before the first sample, `sampledAt` is null. |
| `GET /api/v1/events` | SSE stream of `snapshot` events with integer IDs and `{revision,state,device,telemetry}`. Heartbeat comments keep idle connections open. A slow reader receives the latest snapshot. Reconnect with `Last-Event-ID` and the previous `X-Ryuo-Stream-Generation` response header. On HTTP 409 `stream_reset`, clear both and reconnect for a fresh snapshot. Session expiry or revocation closes an authenticated stream. |
| `POST /api/v1/device/resume` | Send `{}`. `202 {"queued":true}` means the worker was notified to re-enumerate. Device status reports the result. |

`phase` runs through `disconnected`, `connecting`, `configuring` and `healthy`. `degraded` indicates a telemetry problem while connected. Inspect `last_error` and per-provider `errors`. A saved revision can be pending while the device is offline.

## Change the screen

| Request | Accepted fields |
| --- | --- |
| `PATCH /api/v1/brightness` | `brightness`, integer 0–102 |
| `PATCH /api/v1/screen` | `screen_mode`, `media`, `playback_modes`, `slots`, `title_colors`, `content_colors`, `opacity`, `rgb_mode`, `rgb_target`, `thermal_source` |
| `PATCH /api/v1/telemetry-settings` | `temperature_unit` (`Celsius` or `Fahrenheit`), `refresh_interval` in seconds (greater than 0, at most 60), `sensor_selectors`, `slots` |

State schema version 1 includes the fields above plus `schema_version`, `revision` and nullable `active_profile`. `Full Screen` has one zone and `Screen Splitting` has two. For each zone supply a list of media filenames, one playback mode (`Single`, `Random` or `Cycle`), and one title and content color (`#RRGGBB` or `#AARRGGBB`). Empty zones require `Single`. Change these arrays together when changing the zone count. `slots` is a six-element array of `{enabled,measurement_id,widget,label}`. Enabled slots require both IDs. The optional label is at most 32 characters. `opacity` ranges from 0 to 100. RGB modes are `off`, `hue` and `thermal`, with targets `title`, `value` and `both`. Use a logical temperature ID for `thermal_source`. The worker samples at the configured interval with a 0.1-second minimum. Periodic SSE publication has a 0.25-second minimum. HID keepalives run every second using the latest bounded payload. Selector objects are described in the [telemetry guide](telemetry.md).

Each of the three PATCH requests and profile apply requires the revision from `GET /api/v1/state`. Send it as an integer in the JSON field `revision` or as an `If-Match` header. If both are supplied they must agree. For example, when the current revision is 7:

```sh
curl http://127.0.0.1:8746/api/v1/state
curl -X PATCH -H 'Content-Type: application/json' -H 'If-Match: "7"' \
  -d '{"brightness":65}' http://127.0.0.1:8746/api/v1/brightness
```

An example response at acceptance:

```json
{"revision":8,"saved":true,"queued":true,"applied":false,"acked":false,"error":null}
```

`saved` confirms persistence. `queued` records acceptance by the worker. `applied` and `acked` report device work and a matching acknowledgement when known. The response is a snapshot of the ticket. A stale revision returns HTTP 409, e.g. `{"error":"revision_conflict","message":"…","expectedRevision":7,"currentRevision":8}`. Fetch state again, reconcile the changes and resubmit against the new revision.

## Profiles

| Request | Body and success response |
| --- | --- |
| `GET /api/v1/profiles` | `{profiles:[…]}` |
| `POST /api/v1/profiles` | Profile object, e.g. `{"slug":"quiet","name":"Quiet","brightness":45}`. Returns 201 `{profile}`. |
| `GET /api/v1/profiles/{slug}` | `{profile}` |
| `PATCH /api/v1/profiles/{slug}` | Changed profile fields, e.g. `{"name":"Evening"}`. Returns `{profile}`. |
| `DELETE /api/v1/profiles/{slug}` | Delete custom profile, 204, empty response. |
| `POST /api/v1/profiles/{slug}/apply` | `{"revision":8}`, or `{}` with `If-Match`. Returns the state mutation result. |
| `POST /api/v1/profiles/{slug}/duplicate` | `{"name":"Night","slug":"night"}`. Omit `slug` to derive it from the name. Returns 201 `{profile}`. |
| `GET /api/v1/profiles/{slug}/export` | Profile JSON object suitable for import. |
| `POST /api/v1/profiles/import` | Exported JSON object with a free slug. Returns 201 `{profile}`. |

Profiles use the screen fields and schema version above plus `slug`, `name` and `factory`. Slugs consist of lowercase ASCII letters/digits separated by single hyphens. Factory examples can be duplicated. Import creates a custom profile. Apply checks both zone playlists against the connected device and returns HTTP 400 with the missing or ambiguous names and zone numbers. A disconnected device retains the saved intent and validates it at its next handshake. Lookups accept a unique case-insensitive match and send the exact on-device spelling.

## Media

| Request | Body and success response |
| --- | --- |
| `GET /api/v1/media` | `{factory:[names],custom:[names],tools:{ffprobe,ffmpeg},adb:{available,reason,serial,targetToken?}}`. Media names come from the current device `conn` descriptor. Disconnected devices have empty listings. |
| `POST /api/v1/media/upload` | Raw file body, `application/octet-stream`, optional descriptive `X-Filename`. For automatic ADB selection send the `X-Ryuo-Media-Target` header from the media listing. The server generates the remote basename and returns 201 for confirmed delivery. |
| `GET /api/v1/media/jobs/{job_id}` | Stored job result from this process. Completed results are bounded and expire by eviction or restart. |
| `GET /api/v1/media/preview/{kind}/{name}` | `thumbnail` gives a JPEG. `proxy` gives a bounded MP4. Requires a listed name, ADB and media tools. |
| `DELETE /api/v1/media/{name}` | Delete one custom file through the worker on the current catalog generation. A disconnected target returns HTTP 409. Expired or superseded commands have no effect. Returns 200 after acknowledgement and refreshed listing. Factory files are protected. |

Upload and delete return `{jobId,name,applied,confirmed,error}`. In automatic mode, `GET /api/v1/media` returns an opaque `adb.targetToken` for the verified USB attachment. Send that exact value on POST. A missing, incorrect or stale token returns 409 `media_target_changed`. Refresh the listing and confirm the displayed target before starting a new upload. The token is kept only in memory and is independent of session authentication and CSRF. Explicit `ANDROID_SERIAL` selection omits the token and accepts an upload without the header.

Upload verifies the target before processing the body, checks it again before transfer, and waits for validation, conversion if needed, ADB push and a refreshed listing. With automatic selection, the USB port and serial must identify the single physical cooler, and the same ADB transport must still be authorized when the transfer starts. HTTP 502 with `confirmed:false` means the operation could not be verified. Inspect the catalog before retrying. Uploads are limited to 256 MiB with a 30-second idle timeout. The media manager admits two concurrent operations.

```sh
media_status=$(curl -fsS http://127.0.0.1:8746/api/v1/media)
printf '%s' "$media_status" | python3 -m json.tool
# Confirm the displayed ADB target before starting the transfer.
target=$(printf '%s' "$media_status" | python3 -c 'import json,sys; print(json.load(sys.stdin)["adb"].get("targetToken", ""))')
curl -H "X-Ryuo-Media-Target: $target" -H 'Content-Type: application/octet-stream' --data-binary @clip.mp4 \
  http://127.0.0.1:8746/api/v1/media/upload
```

## Authentication and errors

| Request | Body and success response |
| --- | --- |
| `GET /api/v1/auth/status` | `{required,authenticated,csrfToken}` and, for LAN password mode, remaining `expiresIn` seconds. |
| `POST /api/v1/auth/login` | `{"password":"…"}` over HTTPS. Returns session status, CSRF token and a session cookie on successful remote login. |
| `POST /api/v1/auth/logout` | `{}`. Send the session cookie and `X-CSRF-Token` for a remote password session. Returns `{"authenticated":false}`. |
| `GET /api/v1/diagnostics` | `{security,session}` reports bind mode, proxy count and session statistics. Omits the verifier, cookie and CSRF token. |

Handled errors usually return `{error,message}`. Common codes are 400 `validation_error`, 401 `authentication_required` or `invalid_credentials`, 403 `forbidden` or `csrf_failed`, 404 `not_found`, 409 `revision_conflict` or `conflict`, 415 `unsupported_media_type`, 429 `media_busy`, 502 `media_operation_failed` and 503 `tool_unavailable` or `media_unavailable`. An unconfirmed media job uses its job result as the 502 body. Unsupported paths or methods can return a standard HTTP error.
