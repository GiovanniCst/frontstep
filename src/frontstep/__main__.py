# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
"""`python -m frontstep` — the way in for whoever installed it into THIS Python.

⚠️ Not a PATH fallback after `uv tool install`: that puts the package in an
environment of its own, where the system Python cannot see it.

Installing Frontstep puts a `frontstep` command in the interpreter's scripts
directory, and on Windows that directory is very often NOT on PATH. pip even
says so while installing:

    WARNING: The script frontstep.exe is installed in '…\\Scripts' which is not
    on PATH.

It warns and moves on, leaving an application that is installed and cannot be
started. Measured on a clean Windows 11: `python` worked, `pip` did not, and
after installing, neither did `frontstep`.

`python -m` needs none of that: the interpreter is already the thing being run.
It is three lines, and it is the difference between an application somebody can
start and one they cannot.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
