# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import subprocess
import threading
import uuid

import pytest

from ryuo_screen.device import DeviceWorker, HidTransport

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux HID process claim")


def test_kernel_claim_is_exclusive_and_released():
    from ryuo_screen.ownership import DeviceOwnership, OwnershipError

    name = "ryuo-test-" + uuid.uuid4().hex
    with DeviceOwnership(name):
        with pytest.raises(OwnershipError, match="owner"):
            with DeviceOwnership(name):
                pytest.fail("another claimant acquired the same name")
    with DeviceOwnership(name):
        pass


def test_external_process_cannot_claim_until_owner_releases():
    from ryuo_screen.ownership import DeviceOwnership

    name = "ryuo-test-" + uuid.uuid4().hex
    command = [sys.executable, "-c", (
        "import sys\n"
        "from ryuo_screen.ownership import DeviceOwnership, OwnershipError\n"
        "try:\n"
        "    with DeviceOwnership(sys.argv[1]):\n"
        "        pass\n"
        "except OwnershipError:\n"
        "    raise SystemExit(42)\n"
    ), name]
    with DeviceOwnership(name):
        assert subprocess.run(command, timeout=3).returncode == 42
    assert subprocess.run(command, timeout=3).returncode == 0


def test_real_hid_transport_claims_before_start_and_releases_after_stop():
    from ryuo_screen.ownership import DeviceOwnership, OwnershipError

    opened = threading.Event()

    class NoDevice:
        def enumerate(self, _vid, _pid):
            opened.set()
            return []

    worker = DeviceWorker(HidTransport(hid_module=NoDevice()), None)
    try:
        with DeviceOwnership():
            with pytest.raises(OwnershipError, match="owner"):
                worker.start()
            assert not opened.is_set()

        worker.start()
        assert opened.wait(1)
        with pytest.raises(OwnershipError):
            with DeviceOwnership():
                pytest.fail("worker in reconnect backoff lost ownership")
    finally:
        worker.stop()
    with DeviceOwnership():
        pass


def test_stop_timeout_preserves_claim_until_successful_stop():
    from ryuo_screen.ownership import DeviceOwnership, OwnershipError

    entered = threading.Event()
    release = threading.Event()

    class BlockingTransport:
        def open(self):
            entered.set()
            release.wait(3)
            raise OSError("no device")

        def close(self):
            pass

    name = "ryuo-test-" + uuid.uuid4().hex
    worker = DeviceWorker(BlockingTransport(), None, ownership=DeviceOwnership(name))
    worker.start()
    try:
        assert entered.wait(1)
        with pytest.raises(TimeoutError):
            worker.stop(timeout=0)
        with pytest.raises(OwnershipError):
            with DeviceOwnership(name):
                pytest.fail("stopping worker lost ownership before close")
    finally:
        release.set()
        worker.stop()
    with DeviceOwnership(name):
        pass
