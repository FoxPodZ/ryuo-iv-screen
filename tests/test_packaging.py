# SPDX-License-Identifier: GPL-3.0-or-later
import configparser
import re
import shlex
from pathlib import Path

from ryuo_screen.store import AppConfig

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"


def test_service_runs_installed_daemon_as_unprivileged_account():
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read(PACKAGING / "ryuo-screen.service")
    assert "Service" in unit
    service = unit["Service"]
    assert service["User"] == service["Group"] == "ryuo-screen"
    argv = shlex.split(service["ExecStart"])
    assert argv[:3] == ["/opt/ryuo-screen/venv/bin/python", "-m", "ryuo_screen.daemon"]
    assert argv[argv.index("--config") + 1] == "/etc/ryuo-screen/config.toml"
    assert argv[argv.index("--web-root") + 1] == "/opt/ryuo-screen/web/dist"
    assert service.getboolean("NoNewPrivileges") and service.getboolean("PrivateTmp")
    assert service["ProtectSystem"] == "strict"
    assert service["Restart"] == "on-failure"
    assert service["DevicePolicy"] == "closed"
    for key in ["RuntimeDirectory", "StateDirectory", "CacheDirectory"]:
        assert service[key] == "ryuo-screen"
    assert set(service["ReadWritePaths"].split()) == {
        "/run/ryuo-screen", "/var/lib/ryuo-screen", "/var/cache/ryuo-screen",
    }


def test_missing_config_uses_documented_loopback_port(tmp_path):
    assert AppConfig.load(tmp_path / 'absent').listen_port == 8746


def test_system_directories_and_loopback_config(tmp_path):
    template = PACKAGING / "config.toml"
    assert template.exists()
    for path in (template, tmp_path / "missing", ROOT / "examples/ryzen-7900x-rx7900xtx.toml"):
        config = AppConfig.load(path)
        assert (config.listen_host, config.listen_port, config.lan_enabled) == ("127.0.0.1", 8746, False)
        assert config.state_path == Path("/var/lib/ryuo-screen/state.json")
    rows = [shlex.split(row) for row in (PACKAGING / "ryuo-screen.tmpfiles").read_text().splitlines()
            if row.startswith("d ")]
    for directory in ("/run/ryuo-screen", "/var/lib/ryuo-screen", "/var/cache/ryuo-screen"):
        assert ["d", directory, "0750", "ryuo-screen", "ryuo-screen"] in [row[:5] for row in rows]


def test_permissions_match_hid_interface_and_both_usb_ids():
    rules = [line for line in (ROOT / "70-ryuo.rules").read_text().splitlines()
             if line and not line.startswith("#")]
    # Interface attributes live on a different ancestor than USB VID/PID.
    assert any('ATTRS{bInterfaceNumber}=="00"' in line and 'ENV{.RYUO_IFACE}="1"' in line
               for line in rules)
    grants = [line for line in rules if 'GROUP=' in line]
    assert len(grants) == 4
    for vendor in ("0b05", "1c75"):
        assert any(all(key in line for key in ('SUBSYSTEM=="hidraw"', 'ENV{.RYUO_IFACE}=="1"',
                   'ATTRS{idVendor}=="' + vendor + '"', 'ATTRS{idProduct}=="1c76"')) for line in grants)
        assert any(all(key in line for key in ('SUBSYSTEM=="usb"', 'ENV{DEVTYPE}=="usb_device"',
                   'ATTR{idVendor}=="' + vendor + '"', 'ATTR{idProduct}=="1c76"')) for line in grants)
    assert all('MODE="0660"' in line and 'GROUP="ryuo-screen"' in line for line in grants)
    assert not any("0666" in line for line in rules)


def test_installer_preserves_legacy_venv_before_building_at_fixed_prefix():
    installer = (ROOT / "scripts/install.sh").read_text()
    backup = 'mv -- "$prefix/venv" "$backup/opt/ryuo-screen/venv"'
    assert backup in installer
    assert installer.index(backup) < installer.index('python3 -m venv "$prefix/venv"')


def test_install_assets_and_keep_persistent_data_unless_purge():
    install = (ROOT / "scripts/install.sh").read_text()
    assert "web/dist" in install and "/opt/ryuo-screen" in install
    uninstall = (ROOT / "scripts/uninstall.sh").read_text()
    assert "purge=no" in uninstall and "1:--purge-data) purge=yes" in uninstall
    purge = uninstall.index('if [ "$purge" = yes ]')
    end_guard = uninstall.index("\nfi", purge)
    for directory in ("/etc/ryuo-screen", "/var/lib/ryuo-screen"):
        deletes = [m.start() for m in re.finditer(r"(?m)^\s*rm\s+[^\n]*" + directory, uninstall)]
        assert deletes and all(purge < position < end_guard for position in deletes)


def test_repeated_uninstall_cannot_remove_a_restored_legacy_unit():
    uninstall = (ROOT / "scripts/uninstall.sh").read_text()
    marker = "/opt/ryuo-screen/.installed"
    assert marker in (ROOT / "scripts/install.sh").read_text()
    guard = 'if [ -f ' + marker + ' ]; then'
    assert guard in uninstall
    assert uninstall.index(guard) < uninstall.index("systemctl disable --now")
    assert "rm -f " + marker in uninstall


def test_operator_guides_cover_registered_api():
    guide = (ROOT / "docs/api.md").read_text()
    api = (ROOT / "ryuo_screen/api.py").read_text()
    routes = re.findall(r'app\.router\.add_(\w+)\(\s*API_PREFIX \+ "([^"]+)"', api)
    assert len(routes) >= 25
    for method, route in routes:
        assert method.upper() + " /api/v1" + route + "`" in guide
    readme = (ROOT / "README.md").read_text()
    for name in ("api", "deployment", "security", "telemetry", "web-ui"):
        assert (ROOT / ("docs/" + name + ".md")).is_file()
        assert "docs/" + name + ".md" in readme


def test_installer_resolves_and_builds_all_wheels_before_stopping_service():
    script = (ROOT / "scripts/install.sh").read_text()
    prepare = 'python3 -m pip wheel --wheel-dir "$wheels" "$src"'
    assert prepare in script
    assert script.index(prepare) < script.index("systemctl stop ryuo-screen.service")
    assert '--no-index --find-links "$wheels"' in script


def test_checkout_overlap_checked_before_runtime_or_service_changes():
    script = (ROOT / "scripts/install.sh").read_text()
    guard = 'if [ "$src" = "$destination" ]'
    assert guard in script
    assert "exit 1" in script[script.index(guard):script.index("getent group")]
    assert script.index(guard) < script.index("systemctl stop ryuo-screen.service")


def test_failed_runtime_replacement_restores_old_paths_and_service_activity():
    script = (ROOT / "scripts/install.sh").read_text()
    assert "systemctl is-active --quiet ryuo-screen.service" in script
    assert "trap finish 0" in script
    assert 'restore_runtime "$prefix/venv"' in script
    assert 'restore_runtime "$prefix/web/dist"' in script
    assert 'if [ "$was_active" = yes ]; then' in script
