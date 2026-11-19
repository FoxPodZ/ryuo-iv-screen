# SPDX-License-Identifier: GPL-3.0-or-later
import configparser
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

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
    backup = 'save_runtime "$prefix/venv" "$venv_hold"'
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
    guard = 'if overlap "$source_path" "$destination"'
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


class InstallerFixture:
    """Run a path-relocated installer with a private, allowlisted command path."""

    def __init__(self, root):
        self.root = root
        self.prefix = root / "opt/ryuo-screen"
        self.src = root / "checkout"
        self.log = root / "calls"
        self.log.touch()
        self.active = root / "active"
        self.active.touch()
        self.bin = root / "bin"
        self.bin.mkdir()
        (self.prefix / "venv/bin").mkdir(parents=True)
        (self.prefix / "venv/bin/python").write_text("old interpreter")
        (self.prefix / "web/dist").mkdir(parents=True)
        (self.prefix / "web/dist/index.html").write_text("old UI")
        (self.src / "web/dist/assets").mkdir(parents=True)
        (self.src / "web/dist/index.html").write_text("new UI")
        scripts = self.src / "scripts"
        scripts.mkdir()
        self.script = scripts / "install.sh"
        # Every system destination in this copy points inside the fixture.
        self.script.write_text(re.sub(r"/(?=opt/|etc/|var/)", str(root) + "/",
                                      (ROOT / "scripts/install.sh").read_text()))
        for name in ("dirname", "realpath", "mktemp", "mkdir", "rm", "cp", "rmdir", "touch"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.stub("id", '[ "$1" != -u ] || echo 0')
        self.stub("getent", "exit 0")
        self.stub("install", 'exec /usr/bin/install "$@"')
        self.stub("python3", 'echo "python $*" >> "$LOG"\n[ "$1 $2" = "-m pip" ]')
        self.stub("systemctl", '''echo "systemctl $*" >> "$LOG"
case "$1" in
    stop) rm -f "$ACTIVE" ;;
    start) [ -f "$PREFIX/venv/bin/python" ] && [ -f "$PREFIX/web/dist/index.html" ] && touch "$ACTIVE" ;;
    is-active) [ -f "$ACTIVE" ] ;;
esac''')
        # Deliver the signal while the installer shell is waiting for mv.
        # The file move has completed, but its next statement has not run.
        self.stub("mv", '''last=; prior=
for arg do prior=$last; last=$arg; done
if [ "$prior" = "$INJECT_PATH" ] && [ "$INJECT_WHEN" = before ]; then
    echo injected >> "$LOG"; kill "-$INJECT_SIGNAL" "$PPID"; exit 1
fi
/usr/bin/mv "$@" || exit 1
if [ "$prior" = "$INJECT_PATH" ]; then
    echo injected >> "$LOG"; kill "-$INJECT_SIGNAL" "$PPID"
fi''')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run(self, resource="", signal="TERM", when="after"):
        return subprocess.run(
            ["/bin/sh", str(self.script)], cwd=self.src,
            env={"PATH": str(self.bin), "TMPDIR": str(self.root), "LOG": str(self.log),
                 "PREFIX": str(self.prefix), "ACTIVE": str(self.active),
                 "INJECT_PATH": str(self.prefix / resource) if resource else "",
                 "INJECT_SIGNAL": signal, "INJECT_WHEN": when}, capture_output=True, text=True,
            timeout=10,
        )


@pytest.mark.parametrize("resource", ["venv", "web/dist"])
@pytest.mark.parametrize("signal", ["TERM", "INT"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_interrupted_move_restores_runtime_and_service(tmp_path, resource, signal, when):
    fixture = InstallerFixture(tmp_path)
    result = fixture.run(resource, signal, when)
    calls = fixture.log.read_text()
    assert result.returncode != 0 and "injected" in calls, (calls, result.stderr)
    assert (fixture.prefix / "venv/bin/python").read_text() == "old interpreter"
    assert (fixture.prefix / "web/dist/index.html").read_text() == "old UI"
    assert "systemctl start" in calls and fixture.active.exists()


@pytest.mark.parametrize("direction", ["source_inside_destination", "destination_inside_source"])
def test_overlapping_symlinked_assets_rejected_before_any_service_or_build(tmp_path, direction):
    fixture = InstallerFixture(tmp_path)
    src = fixture.src / "web/dist"
    dest = fixture.prefix / "web/dist"
    if direction == "source_inside_destination":
        shutil.move(str(src), str(dest / "source"))
        src.symlink_to(dest / "source", target_is_directory=True)
    else:
        shutil.move(str(dest), str(src / "installed"))
        dest.symlink_to(src / "installed", target_is_directory=True)
    result = fixture.run()
    assert result.returncode != 0
    assert fixture.log.read_text() == "", result.stderr
    assert fixture.active.exists()
    assert (src / "index.html").read_text() == "new UI"
    assert (dest / "index.html").read_text() == "old UI"
