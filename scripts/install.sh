#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
umask 022
[ "$(id -u)" = 0 ] || { echo "Run the installer as root." >&2; exit 1; }
[ "$#" = 0 ] || { echo "Usage: install.sh" >&2; exit 2; }
src=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
prefix=/opt/ryuo-screen
unit=/etc/systemd/system/ryuo-screen.service
[ -r "$src/web/dist/index.html" ] && [ -d "$src/web/dist/assets" ] || {
    echo "Build the Web UI in web/ before installing." >&2; exit 1;
}

getent group ryuo-screen >/dev/null || groupadd --system ryuo-screen
id ryuo-screen >/dev/null 2>&1 || useradd --system --gid ryuo-screen \
    --home-dir /var/lib/ryuo-screen --no-create-home --shell /usr/sbin/nologin ryuo-screen
install -d -m 0755 "$prefix" "$prefix/web"
mkdir -p /etc/systemd/system /etc/tmpfiles.d /etc/udev/rules.d
if systemctl cat ryuo-screen.service >/dev/null 2>&1; then
    systemctl stop ryuo-screen.service
fi

# Keep the previous unit and all operator data together, accessible only to root.
install -d -m 0700 /var/backups/ryuo-screen
backup=$(mktemp -d /var/backups/ryuo-screen/install.XXXXXXXX)
echo "Pre-install backup: $backup"
for path in "$unit" "$unit.d" /etc/ryuo-screen /var/lib/ryuo-screen /etc/udev/rules.d/70-ryuo.rules /etc/tmpfiles.d/ryuo-screen.conf; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        cp -a --parents -- "$path" "$backup"
    fi
done

# A legacy ExecStart can use this same interpreter. Preserve its environment
# at its original layout in the backup and install into a fresh directory.
install -d -m 0700 "$backup/opt/ryuo-screen/web"
if [ -e "$prefix/venv" ] || [ -L "$prefix/venv" ]; then
    mv -- "$prefix/venv" "$backup/opt/ryuo-screen/venv"
fi
if [ -e "$prefix/web/dist" ] || [ -L "$prefix/web/dist" ]; then
    mv -- "$prefix/web/dist" "$backup/opt/ryuo-screen/web/dist"
fi
python3 -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install --disable-pip-version-check "$src"
install -d -m 0755 "$prefix/web/dist" "$prefix/web/dist/assets"
install -m 0644 "$src"/web/dist/assets/* "$prefix/web/dist/assets/"
install -m 0644 "$src/web/dist/index.html" "$prefix/web/dist/index.html"
install -m 0644 "$src/LICENSE" "$src/LICENSE-ADDITIONAL-TERMS.md" "$prefix/"
install -d -o root -g ryuo-screen -m 0750 /etc/ryuo-screen
if [ ! -e /etc/ryuo-screen/config.toml ]; then
    install -o root -g ryuo-screen -m 0640 "$src/packaging/config.toml" /etc/ryuo-screen/config.toml
fi
install -m 0644 "$src/70-ryuo.rules" /etc/udev/rules.d/70-ryuo.rules
install -m 0644 "$src/packaging/ryuo-screen.tmpfiles" /etc/tmpfiles.d/ryuo-screen.conf
install -m 0644 "$src/packaging/ryuo-screen.service" "$unit"
install -m 0644 /dev/null /opt/ryuo-screen/.installed
systemd-tmpfiles --create /etc/tmpfiles.d/ryuo-screen.conf
udevadm control --reload-rules
systemctl daemon-reload
systemctl enable --now ryuo-screen.service
echo "Replug the cooler to apply USB permissions. See docs/deployment.md."
