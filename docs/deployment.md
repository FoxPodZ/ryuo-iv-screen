<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Install the Linux system service

The daemon runs as the `ryuo-screen` system account. A single device worker owns HID from handshake through shutdown. Python 3.8+ and systemd are required. ADB, ffprobe and FFmpeg enable upload and preview. The checked-in browser bundle runs without Node.js.

## Install on Fedora

Use a trusted checkout outside `/opt/ryuo-screen`. The installer creates the account, installs the Python package into `/opt/ryuo-screen/venv`, copies `web/dist` into `/opt/ryuo-screen/web/dist`, installs the unit and rules, then enables and starts the service.

```sh
sudo dnf install python3 python3-pip hidapi android-tools ffmpeg-free
sudo ./scripts/install.sh
systemctl status ryuo-screen.service
curl http://127.0.0.1:8746/api/v1/device
```

Replug the cooler to apply its new USB permissions. Open [the local UI](http://127.0.0.1:8746/). Fedora packages the Android platform tools and FFmpeg separately. For conversion, check the encoders available in your installed build. [Fedora android-tools](https://packages.fedoraproject.org/pkgs/android-tools/android-tools/) · [Fedora ffmpeg-free](https://packages.fedoraproject.org/pkgs/ffmpeg/ffmpeg-free/)

| Location | Contents and ownership |
| --- | --- |
| `/opt/ryuo-screen/venv`, `/opt/ryuo-screen/web/dist` | Root-managed service code and browser bundle |
| `/etc/ryuo-screen/config.toml` | Static configuration, root-owned, group `ryuo-screen` can read (0640) |
| `/run/ryuo-screen/control.sock` | Local HTTP socket (0660), recreated at startup |
| `/var/lib/ryuo-screen/state.json` | Desired screen state and revision |
| `/var/lib/ryuo-screen/profiles/*.json` | Custom profiles, including selector overrides |
| `/var/cache/ryuo-screen` | Temporary upload, conversion and preview files |
| `/var/backups/ryuo-screen/install.*` | Root-only pre-install config, data, rules, local unit, venv and UI bundle when present |

The unit and tmpfiles create runtime, state and cache directories owned by `ryuo-screen` with mode 0750. The system filesystem is read-only to the daemon except its service directories and private temporary area. A nonstandard `data_dir` also needs ownership, SELinux labeling and a matching systemd `ReadWritePaths` override. Back up custom locations separately.

## Operate and diagnose

```sh
sudo systemctl stop ryuo-screen.service
sudo systemctl start ryuo-screen.service
systemctl status ryuo-screen.service
journalctl -u ryuo-screen.service -b
journalctl -fu ryuo-screen.service
curl http://127.0.0.1:8746/api/v1/media
command -v adb ffmpeg ffprobe
ffmpeg -encoders | grep -E 'libx265|libx264|png|mjpeg'
```

The media response reports the actual ADB selection and available executables. The unit isolates its ADB server on `/run/ryuo-screen/adb.sock`. With the service running, open Media first, then check the same server as the service account:

```sh
sudo -u ryuo-screen env HOME=/var/lib/ryuo-screen \
  ADB_SERVER_SOCKET=localfilesystem:/run/ryuo-screen/adb.sock adb devices -l
```

Automatic selection requires one physical Ryuo USB device (PID `1c76`, VID `0b05` or `1c75`). The daemon matches its sysfs USB port and serial against an authorized `adb devices -l` entry and binds the media listing to that transport ID with a temporary target token. The browser includes the token with the upload. After a target change, refresh the listing and confirm the new device before starting another transfer. If the device changes during conversion, the job fails before transfer. When the USB serial, port metadata or transport ID is missing, or multiple coolers are attached, explicitly select the intended device. Set `Environment=ANDROID_SERIAL=<cooler-serial>` in a `[Service]` drop-in via `sudo systemctl edit ryuo-screen.service`, then restart. A second host ADB server holding the USB interface can prevent discovery. Close its session before retrying. Missing encoders can affect conversions even when `tools.ffmpeg` is true.

For HID permission errors, use `udevadm info --attribute-walk --name=/dev/hidrawN` with the actual node, and inspect its group and mode using `ls -l`. Product `1c76` uses VID `0b05` or `1c75`. Only interface `00` receives the hidraw grant. ADB requires usbfs access to the matching composite USB device. The systemd device allowlist permits hidraw and USB character devices, and NVIDIA frontend devices for optional telemetry. Filesystem permissions still apply. If a device group first appeared in `/proc/devices` after daemon startup, restart the unit once to resolve the group. The shipped HID rule retains the logged-in seat ACL. Joining the `ryuo-screen` group grants local socket control **and** device access.

A worker reconnects after USB loss or a suspend/boottime gap. Retire any old sleep hook that starts another HID writer. An optional existing post-resume hook can wake the worker more promptly:

```sh
if [ "$1" = post ]; then
    curl --fail --silent --show-error --max-time 2 \
      --unix-socket /run/ryuo-screen/control.sock \
      -H 'Content-Type: application/json' -d '{}' http://localhost/api/v1/device/resume
fi
```

## Update and migrate the existing unit

1. Record `systemctl cat ryuo-screen.service` and `systemctl show -p FragmentPath -p DropInPaths -p ExecStart ryuo-screen.service`. Keep the previous checkout, its environment, and any files named by the old command. A legacy install may run scripts under `/home/ephdtrg/ryuo-iv-screen-linux`. The installed unit retains the same service name.
2. Review local drop-ins for old `ExecStart`, user, path or sleep-hook overrides. Save and move conflicting overrides outside the unit search path before starting the new service, and run `sudo systemctl daemon-reload`. Stop competing direct sessions, including independently managed user services.
3. From the desired revision rerun `sudo ./scripts/install.sh`. The installer first builds a local wheel cache while the previous service runs. It then stops an existing system unit, saves its local unit files and the standard configuration/state into the printed backup directory, then renames the old venv and bundle within their respective filesystems and copies them into the backup before installing fresh copies. The replacement venv installs from the prepared wheels. On a setup failure the installer attempts to restore replaced files, restores the previous runtime and restarts a previously active service. An existing config stays in place. Keep the backup until the updated service works. For a UI changed locally, run `npm --prefix web ci` and `npm --prefix web run build` as your normal user first, using a Node version supported by the locked dependencies.
4. Confirm that any pre-existing config is readable by the service account (for a standard file, root:ryuo-screen, mode 0640). Compare `systemctl show -p User -p ExecStart ryuo-screen.service` against the packaged unit. Inspect the device, sensors and media pages. The default browser port is **8746**. An existing explicit `listen_port = 9077` still takes effect unless you edit the TOML and restart.

## Roll back or uninstall

For an earlier packaged release, stop the service, run its installer from its matching checkout and restart with its compatible configuration. Restore state and profiles from the selected backup while stopped if needed. Keep a copy of any more recent edits before replacing them.

For a legacy home-directory deployment, stop the new service and run `sudo ./scripts/uninstall.sh`. Restore the original unit to its recorded `FragmentPath`, original drop-ins to their recorded paths, and original USB rules and config if required. The installer backup mirrors the original absolute paths below its directory. If the old command used the same venv, copy its saved directory back to the original path after uninstall, e.g. `sudo cp -a -- "$BACKUP/opt/ryuo-screen/venv" /opt/ryuo-screen/`. Restoring the original path keeps venv script interpreters valid. For example, if the old fragment lived under `/etc/systemd/system`, restore it with:

```sh
# Set BACKUP to the exact pre-migration directory printed by install.sh.
sudo cp -a -- "$BACKUP/etc/systemd/system/ryuo-screen.service" /etc/systemd/system/
sudo systemctl daemon-reload
systemctl show -p User -p ExecStart ryuo-screen.service
sudo udevadm control --reload-rules
sudo systemctl enable --now ryuo-screen.service
```

Verify the restored `ExecStart` includes the original interpreter, home-checkout path and arguments before starting. Replug after restoring rules. A vendor fragment shadowed by the installed unit becomes visible again after the local unit is removed.

Ordinary uninstall removes the installed service runtime, UI, cache and rules. It keeps configuration, state, profiles, account and backups. Use `sudo ./scripts/uninstall.sh --purge-data` only to erase the standard config and data directories too. Existing pre-install backups are root-owned and have an independent retention policy.

## Fedora SELinux

Keep enforcing mode active. Compare a failing action with its timestamps in the service journal and audit log:

```sh
getenforce
sudo ausearch -m AVC,USER_AVC -ts recent -i
ls -Zd /opt/ryuo-screen /etc/ryuo-screen /var/lib/ryuo-screen /var/cache/ryuo-screen
sudo restorecon -Rv /opt/ryuo-screen /etc/ryuo-screen /var/lib/ryuo-screen /var/cache/ryuo-screen
```

Check the denied source domain, target type, class and permission against the operation. Verify ordinary ownership, the systemd device allowlist and udev matching before changing SELinux. For custom paths, register a persistent file-context mapping to the matching standard location and apply `restorecon`. If a denial persists with correct labels, reproduce only that operation and have the administrator review a local policy scoped to the observed domain, target type, class and permission. Test the exact action again and recheck AVCs. Avoid installing policy generated from unrelated audit history.
