#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
umask 022
[ "$(id -u)" = 0 ] || { echo "Run the installer as root." >&2; exit 1; }
[ "$#" = 0 ] || { echo "Usage: install.sh" >&2; exit 2; }
src=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
prefix=/opt/ryuo-screen
unit=/etc/systemd/system/ryuo-screen.service
[ -r "$src/web/dist/index.html" ] && [ -d "$src/web/dist/assets" ] || {
    echo "Build the Web UI in web/ before installing." >&2; exit 1;
}

# Compare real path components in both directions, including an existing
# destination symlink whose target is outside the installation prefix.
overlap() {
    case "$1/" in "${2%/}/"*) return 0 ;; esac
    case "$2/" in "${1%/}/"*) return 0 ;; esac
    return 1
}
for output in "$prefix" "$prefix/venv" "$prefix/web/dist"; do
    destination=$(realpath -m -- "$output")
    for input in "$src" "$src/web/dist" "$src/web/dist/assets" "$src/web/dist/index.html" "$src"/web/dist/assets/*; do
        source_path=$(realpath -m -- "$input")
        if overlap "$source_path" "$destination"; then
            echo "Source $source_path overlaps installation path $destination." >&2
            exit 1
        fi
    done
done

# Resolve, download and build the project and every dependency while the old
# service is still running. After cutover starts pip can use local wheels only.
wheels=$(mktemp -d)
trap 'rm -rf -- "$wheels"' 0
trap 'exit 1' HUP INT TERM
python3 -m pip wheel --wheel-dir "$wheels" "$src"

getent group ryuo-screen >/dev/null || groupadd --system ryuo-screen
id ryuo-screen >/dev/null 2>&1 || useradd --system --gid ryuo-screen \
    --home-dir /var/lib/ryuo-screen --no-create-home --shell /usr/sbin/nologin ryuo-screen
install -d -m 0755 "$prefix" "$prefix/web"
mkdir -p /etc/systemd/system /etc/tmpfiles.d /etc/udev/rules.d
# Keep the previous unit and all operator data together, accessible only to root.
install -d -m 0700 /var/backups/ryuo-screen
backup=$(mktemp -d /var/backups/ryuo-screen/install.XXXXXXXX)
echo "Pre-install backup: $backup"
was_active=no
if systemctl is-active --quiet ryuo-screen.service; then
    was_active=yes
fi
venv_hold=
web_hold=
replace_files=no
rule=/etc/udev/rules.d/70-ryuo.rules
tmpfiles=/etc/tmpfiles.d/ryuo-screen.conf
marker=/opt/ryuo-screen/.installed
config=/etc/ryuo-screen/config.toml
created_config=no

# Each holder is a sibling of the path being replaced. rename(2) is atomic
# on that filesystem. The presence of original is the rollback record, even
# if the shell receives a signal before mv returns to this script.
save_runtime() {
    if [ -e "$1" ] || [ -L "$1" ]; then
        mv -T -- "$1" "$2/original"
        cp -aT -- "$2/original" "$backup$1"
    else
        touch "$2/was-absent"
    fi
}

restore_runtime() {
    [ -n "$2" ] || return 0
    if [ -e "$2/original" ] || [ -L "$2/original" ]; then
        rm -rf -- "$1" && mv -T -- "$2/original" "$1" || return 1
    elif [ -f "$2/was-absent" ]; then
        rm -rf -- "$1" || return 1
    fi
    rm -rf -- "$2"
}

finish() {
    status=$?
    trap '' HUP INT TERM
    trap - 0
    if [ "$status" -ne 0 ]; then
        # Continue independent recovery steps if restoring a rule or reloading
        # udev also fails (for example when the service bus is unavailable).
        set +e
        echo "Install failed. Restoring the previous deployment from $backup." >&2
        if [ "$replace_files" = yes ]; then
            if systemctl cat ryuo-screen.service >/dev/null 2>&1; then
                systemctl stop ryuo-screen.service
            fi
            for path in "$unit" "$rule" "$tmpfiles" "$marker"; do
                if [ -e "$backup$path" ] || [ -L "$backup$path" ]; then
                    cp -aT --remove-destination -- "$backup$path" "$path"
                else
                    rm -f -- "$path"
                fi
            done
            if [ "$created_config" = yes ]; then rm -f -- "$config"; fi
            systemctl daemon-reload
            udevadm control --reload-rules
        fi
        restore_runtime "$prefix/venv" "$venv_hold"
        restore_runtime "$prefix/web/dist" "$web_hold"
        if [ "$was_active" = yes ]; then
            systemctl start ryuo-screen.service
        fi
    else
        rm -rf -- "$venv_hold" "$web_hold"
    fi
    rm -rf -- "$wheels"
    exit "$status"
}
trap finish 0
if systemctl cat ryuo-screen.service >/dev/null 2>&1; then
    systemctl stop ryuo-screen.service
fi

for path in "$unit" "$unit.d" /etc/ryuo-screen /var/lib/ryuo-screen "$rule" "$tmpfiles" "$marker"; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        cp -a --parents -- "$path" "$backup"
    fi
done

# A legacy ExecStart can use this same interpreter. Preserve its environment
# at its original layout in the backup and install into a fresh directory.
install -d -m 0700 "$backup/opt/ryuo-screen/web"
venv_hold=$(mktemp -d "$prefix/.previous.XXXXXXXX")
web_hold=$(mktemp -d "$prefix/web/.previous.XXXXXXXX")
save_runtime "$prefix/venv" "$venv_hold"
save_runtime "$prefix/web/dist" "$web_hold"
python3 -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install --no-index --find-links "$wheels" ryuo-iv-screen
install -d -m 0755 "$prefix/web/dist" "$prefix/web/dist/assets"
install -m 0644 "$src"/web/dist/assets/* "$prefix/web/dist/assets/"
install -m 0644 "$src/web/dist/index.html" "$prefix/web/dist/index.html"
install -m 0644 "$src/LICENSE" "$src/LICENSE-ADDITIONAL-TERMS.md" "$prefix/"
replace_files=yes
if [ ! -d /etc/ryuo-screen ]; then
    install -d -o root -g ryuo-screen -m 0750 /etc/ryuo-screen
fi
if [ ! -e /etc/ryuo-screen/config.toml ] && [ ! -L /etc/ryuo-screen/config.toml ]; then
    created_config=yes
    install -o root -g ryuo-screen -m 0640 "$src/packaging/config.toml" /etc/ryuo-screen/config.toml
fi
install -m 0644 "$src/70-ryuo.rules" /etc/udev/rules.d/70-ryuo.rules
install -m 0644 "$src/packaging/ryuo-screen.tmpfiles" /etc/tmpfiles.d/ryuo-screen.conf
install -m 0644 "$src/packaging/ryuo-screen.service" "$unit"
install -m 0644 /dev/null /opt/ryuo-screen/.installed
systemd-tmpfiles --create /etc/tmpfiles.d/ryuo-screen.conf
udevadm control --reload-rules
systemctl daemon-reload
systemctl start ryuo-screen.service
systemctl enable ryuo-screen.service
echo "Replug the cooler to apply USB permissions. See docs/deployment.md."
