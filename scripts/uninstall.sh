#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
purge=no
case "$#:${1-}" in
    0:) ;;
    1:--purge-data) purge=yes ;;
    *) echo "Usage: uninstall.sh [--purge-data]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo "Run the uninstaller as root." >&2; exit 1; }
if [ -f /opt/ryuo-screen/.installed ]; then
    if systemctl cat ryuo-screen.service >/dev/null 2>&1; then
        systemctl disable --now ryuo-screen.service
    fi
    rm -f /etc/systemd/system/ryuo-screen.service /etc/udev/rules.d/70-ryuo.rules /etc/tmpfiles.d/ryuo-screen.conf
    systemctl daemon-reload
    udevadm control --reload-rules
    rm -rf /opt/ryuo-screen/venv /opt/ryuo-screen/web/dist /var/cache/ryuo-screen /run/ryuo-screen
    rm -f /opt/ryuo-screen/LICENSE /opt/ryuo-screen/LICENSE-ADDITIONAL-TERMS.md
    rm -f /opt/ryuo-screen/.installed
fi
if [ "$purge" = yes ]; then
    rm -rf /etc/ryuo-screen /var/lib/ryuo-screen
fi
echo "Replug the cooler to remove the installed USB permissions."
