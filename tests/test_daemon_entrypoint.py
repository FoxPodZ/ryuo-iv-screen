# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid

import aiohttp
import pytest

from ryuo_screen.store import ScreenState, StateStore

ROOT = Path(__file__).resolve().parents[1]


def test_module_help_exits_before_importing_hid(tmp_path):
    (tmp_path / "hid.py").write_text("raise AssertionError('help imported hid')\n")
    result = subprocess.run(
        [sys.executable, "-m", "ryuo_screen.daemon", "--help"], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--config" in result.stdout and "--web-root" in result.stdout


@pytest.mark.asyncio
async def test_service_loads_state_serves_both_sites_and_stops_on_sigterm(tmp_path):
    # Replace only hardware enumeration and isolate the process ownership claim.
    (tmp_path / "hid.py").write_text("def enumerate(*args): return []\n")
    claim_name = "ryuo-test-" + uuid.uuid4().hex
    bootstrap = (
        "import functools,runpy; import ryuo_screen.device as device; "
        "device.DeviceOwnership=functools.partial(device.DeviceOwnership, " + repr(claim_name) + "); "
        "runpy.run_module('ryuo_screen.daemon', run_name='__main__')"
    )
    state_dir = tmp_path / "state"
    StateStore(state_dir / "state.json").save(ScreenState(brightness=61, revision=4))
    web_root = tmp_path / "bundle"
    web_root.mkdir()
    (web_root / "index.html").write_text("service UI")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = tmp_path / "config.toml"
    config.write_text('data_dir = "{}"\nlisten_port = {}\n'.format(state_dir, port))
    socket_path = tmp_path / "ctrl.sock"
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", bootstrap, "--config", str(config), "--socket", str(socket_path),
        "--web-root", str(web_root), cwd=str(tmp_path),
        env={**os.environ, "PYTHONPATH": str(ROOT)}, stderr=asyncio.subprocess.PIPE,
    )
    try:
        for _ in range(250):
            if socket_path.is_socket() or process.returncode is not None:
                break
            await asyncio.sleep(0.02)
        assert socket_path.is_socket(), (
            (await process.stderr.read()).decode() if process.returncode is not None else "startup timed out"
        )
        async with aiohttp.ClientSession() as tcp:
            async with tcp.get("http://127.0.0.1:{}/".format(port)) as response:
                assert await response.text() == "service UI"
        async with aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=str(socket_path))) as uds:
            async with uds.get("http://localhost/api/v1/state") as response:
                state = await response.json()
                assert state["revision"] == 4 and state["state"]["brightness"] == 61
            async with uds.get("http://localhost/api/v1/device") as response:
                assert (await response.json())["phase"] != "stopped"
        process.terminate()
        assert await asyncio.wait_for(process.wait(), timeout=5) == 0
        assert not socket_path.exists()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@pytest.mark.parametrize("vendor", ["0b05", "1c75"])
def test_auto_adb_pins_matching_physical_cooler_and_refuses_replacement(tmp_path, monkeypatch, vendor):
    from ryuo_screen import media

    usb = tmp_path / "usb"
    cooler = usb / "1-2.3"
    cooler.mkdir(parents=True)
    (cooler / "idVendor").write_text(vendor)
    (cooler / "idProduct").write_text("1c76")
    (cooler / "serial").write_text("COOLER")
    monkeypatch.setattr(media, "USB_DEVICES", usb, raising=False)
    devices = ["COOLER device usb:1-2.3 product:cm16 transport_id:37"]
    transfers = []

    def adb(argv, **kwargs):
        if argv[1:] == ["devices", "-l"]:
            output = "List of devices attached\n" + "\n".join(devices)
            return subprocess.CompletedProcess(argv, 0, output, "")
        transfers.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    backend = media.AdbBackend(which=lambda _: "adb", runner=adb)
    assert backend.available().serial == "COOLER"
    assert backend.push(tmp_path / "clip.mp4", "user.mp4")
    assert transfers == [["adb", "-t", "37", "push", str(tmp_path / "clip.mp4"),
                          "/sdcard/pcMedia/user.mp4"]]
    # A different device is now authorized, even with the same USB port or serial.
    for replacement in (
        "emulator-5554 device transport_id:38",
        "PHONE device usb:1-2.3 transport_id:38",
        "COOLER device usb:2-1 transport_id:38",
        "COOLER device usb:1-2.3",
    ):
        devices[:] = [replacement]
        assert not backend.available().available
        assert not backend.push(tmp_path / "clip.mp4", "user.mp4")
    assert len(transfers) == 1


def test_auto_adb_rejects_lone_unidentified_android_device(tmp_path, monkeypatch):
    from ryuo_screen import media

    monkeypatch.setattr(media, "USB_DEVICES", tmp_path, raising=False)
    ran = []
    def adb(argv, **kwargs):
        ran.append(argv)
        return subprocess.CompletedProcess(argv, 0, "List of devices attached\nOTHER device transport_id:1\n", "")

    backend = media.AdbBackend(which=lambda _: "adb", runner=adb)
    assert not backend.push(tmp_path / "clip", "user.mp4")
    assert ran == [["adb", "devices", "-l"]]
