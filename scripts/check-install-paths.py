# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject install inputs whose lookup depends on a runtime being replaced."""

import os
import sys
from collections import deque
from pathlib import Path


def check_source(source, destinations):
    # Walk links component by component. A final resolve() alone loses the
    # intermediate directories that must survive until installation completes.
    pending = deque(source.parts)
    current = Path("/")
    links = 0
    while pending:
        part = pending.popleft()
        if part in ("/", "//"):
            current = Path("/")
        elif part == "..":
            current = current.parent
        else:
            current = current / part
        if current in destinations:
            raise ValueError("Source {} traverses installation path {}.".format(source, current))
        if current.is_symlink():
            links += 1
            if links > 40:
                raise ValueError("Too many symlinks in install source {}.".format(source))
            target = Path(os.readlink(current))
            current = current.parent
            pending.extendleft(reversed(target.parts))

    if any(current in destination.parents for destination in destinations):
        raise ValueError("Source {} contains an installation path.".format(source))


def main():
    prefix = Path(sys.argv[1])
    destinations = set()
    for path in (prefix, prefix / "venv", prefix / "web/dist"):
        # Protect both the entry moved during cutover and its resolved target.
        destinations.add(path.parent.resolve() / path.name)
        destinations.add(path.resolve())
    for source in sys.argv[2:]:
        check_source(Path(source), destinations)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(str(exc))
