<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Discover and select sensors

Open Settings or read `GET /api/v1/sensors` to see the current worker catalog. Each sensor has a logical `measurementId`, a unit, a stable `ref`, a source path or tool and availability. Read `GET /api/v1/telemetry` for the cached values and per-provider errors. The collector reprobes periodically and after device recovery. While disconnected, a sample can be absent or stale. Check `sampledAt` and device health together.

| Provider ID | Device and readings |
| --- | --- |
| `amd` | PCI domain:bus:device.function bound to `amdgpu`. Reads GPU load, edge/junction temperature, core/memory clock, power, fan RPM, VRAM used/total through sysfs. Only kernel-exposed readings are available. |
| `nvidia` | NVIDIA UUID discovered using `nvidia-smi`. Load, temperature, power, graphics clock, fan percentage and optional VRAM readings. Static selection also accepts a reported index. |
| `cpu` | Device `host`. Logical IDs include `cpu.load`, `cpu.frequency`, `cpu.temperature`, `cpu.temperature.package` and `cpu.power`. For Ryzen, normal CPU temperature prefers Tdie then Tctl, and package temperature prefers Tctl then Tdie. |
| `hwmon` | Resolved physical chip path plus chip name and input channel, e.g. `platform/nct6775.656/nct6799` and `temp2`. Reads board temperature and fans. The catalog exposes labels and units. |

### Ryzen 9 7900X, RX 7900 XTX and nct6799

```sh
curl -s http://127.0.0.1:8746/api/v1/sensors | python3 -m json.tool
```

Match the RX 7900 XTX in the AMD descriptor metadata and copy its actual PCI BDF. In automatic selection the AMD provider prefers the device with the largest reported VRAM, with PCI address as a tie-breaker. A discrete GPU and a Ryzen integrated GPU can both appear. Choose the intended board temperature from the `hwmon` entries by chip, label and physical channel. A `temp2` label can mean different things on different boards.

For example, **if your catalog reports these references**, the static part of `/etc/ryuo-screen/config.toml` can include:

```toml
gpu_provider = "amd"
gpu_selector = "0000:03:00.0"

[motherboard_sensor]
provider = "hwmon"
device = "platform/nct6775.656/nct6799"
channel = "temp2"
```

Restart after changing static settings. Settings and profiles can override them at runtime using `PATCH /api/v1/telemetry-settings` with the current revision. `sensor_selectors` replaces the entire mapping:

```json
{"revision":8,"sensor_selectors":{"gpu":{"provider":"amd","device":"0000:03:00.0","channel":"gpu.temperature"},"motherboard":{"provider":"hwmon","device":"platform/nct6775.656/nct6799","channel":"temp2"}}}
```

An empty mapping clears the persisted overrides. Copy the three `ref` fields from the catalog, since `hwmonN` and `cardN` numbers can change at boot. A missing selected device is reported as unavailable until it returns or the selection changes. The [sample TOML](../examples/ryzen-7900x-rx7900xtx.toml) includes a BDF placeholder that you must replace.

### Readings on the panel

The API represents an unavailable measurement with `available:false`, `value:null` and an error where known. It can also report a provider error with no measurements. Only the legacy HID payload substitutes numeric zero where a numeric field is required. A zero on the panel alone therefore cannot diagnose an idle or missing sensor.

The dashboard can display `gpu.vram.used` and `gpu.vram.total` in bytes. The firmware has six stock slots and no native VRAM unit. Custom fan widgets always render RPM. Use the dashboard for VRAM and assign supported temperature, load, clock or fan widgets on the panel.
