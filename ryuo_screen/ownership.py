# SPDX-License-Identifier: GPL-3.0-or-later
"""Process-wide HID arbitration on Linux.

The abstract socket is scoped to the Linux network namespace. On other
platforms direct mode retains the legacy behavior without a process lock.
"""

import errno
import socket
import sys


DEFAULT_CLAIM = "ryuo-screen-hid-owner-v1"


class OwnershipError(RuntimeError):
    """The caller could not establish exclusive HID ownership."""


class DeviceOwnership:
    def __init__(self, name: str = DEFAULT_CLAIM) -> None:
        self._address = "\0" + name
        self._socket = None

    def acquire(self) -> None:
        if sys.platform != "linux":
            return
        if self._socket is not None:
            raise OwnershipError("this HID owner already holds the claim")
        claim = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            claim.bind(self._address)
        except OSError as exc:
            claim.close()
            if exc.errno == errno.EADDRINUSE:
                raise OwnershipError(
                    "another Ryuo HID owner is active. Use a service command, "
                    "or stop the service or other direct session before opening HID."
                ) from exc
            raise OwnershipError("could not claim exclusive Ryuo HID ownership: {}".format(exc)) from exc
        self._socket = claim

    def release(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self) -> "DeviceOwnership":
        self.acquire()
        return self

    def __exit__(self, *_exc) -> None:
        self.release()
