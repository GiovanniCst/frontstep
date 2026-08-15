"""What the tests need before they can run anywhere but Linux.

Each helper asks about the PROPERTY it needs — of the filesystem it is about to
write to, of the stream it is about to print on — and never about the name of
the operating system. `sys.platform == "win32"` is a guess about what a system
can do; `chmod` it and read it back is an answer. macOS is case-insensitive by
default and case-sensitive if formatted that way, Windows per-directory since
1803, and a Linux box can mount either: the platform name would be the wrong
question on all three.
"""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

import pytest

# An absolute path, for the tests where a root has to pass validation and
# nothing else about it matters. ⚠️ `/tmp/x` is not one on Windows — a path
# there needs a drive letter — so seven tests raised `ConfigInvalid` before
# reaching the thing they were actually about, and reported it as a defect in
# the configuration parser. It does not need to exist; nothing here looks.
ANY_ABSOLUTE = str(Path(tempfile.gettempdir()) / "x")


def pretend_home(tmp_path: Path, monkeypatch) -> Path:
    """Make `tmp_path` look like the home folder, on every system.

    ⚠️ `HOME` alone is not enough: `ntpath.expanduser`, the code that runs on
    Windows, reads `USERPROFILE` then `HOMEDRIVE`+`HOMEPATH` and never looks at
    `HOME`. `Path.home` is patched too — it is what the code calls by name, and
    left alone a test would write in the real home.
    """
    drive, tail = os.path.splitdrive(str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOMEDRIVE", drive)
    monkeypatch.setenv("HOMEPATH", tail or str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def tells_case_apart(folder: Path) -> bool:
    """Whether this filesystem tells `a` from `A`, asked where it matters."""
    probe = folder / "frontstep-Case-Probe"
    probe.write_text("", encoding="utf-8")
    try:
        return not (folder / "frontstep-case-probe").exists()
    finally:
        probe.unlink()


def keeps_permissions(folder: Path) -> bool:
    """Whether a mode set on a file is a mode the system gives back."""
    probe = folder / "frontstep-mode-probe"
    probe.write_text("", encoding="utf-8")
    try:
        probe.chmod(0o640)
        return stat.S_IMODE(probe.stat().st_mode) == 0o640
    except (OSError, NotImplementedError):
        return False
    finally:
        probe.unlink()


def can_be_a_folder_name(folder: Path, name: str) -> bool:
    """Whether this system will accept a folder called that.

    `|`, `"`, `:` and friends are ordinary characters in a POSIX name and
    forbidden in a Windows one, so a test that builds a folder called `prog|tee`
    to prove the name is never handed to a shell cannot build it there at all.
    """
    try:
        target = folder / name
        target.mkdir()
        target.rmdir()
        return True
    except (OSError, ValueError):
        return False


@pytest.fixture
def case_sensitive_fs(tmp_path):
    """For the tests about a document whose name is spelled the wrong way."""
    if not tells_case_apart(tmp_path):
        pytest.skip(
            "this filesystem does not tell `a` from `A`, so `current_status.md` "
            "and `CURRENT_STATUS.md` are one file here and the question this "
            "test asks does not exist")


@pytest.fixture
def posix_permissions(tmp_path):
    """For the tests that a write keeps the mode the file already had."""
    if not keeps_permissions(tmp_path):
        pytest.skip("this filesystem does not keep a POSIX mode to preserve")


@pytest.fixture
def posix_paths():
    """For the tests written around a path like `/srv/repos`.

    Not portability laziness: on Windows that string is not an absolute path at
    all — it has no drive — and Frontstep is right to refuse it there. The test
    is about how such a path READS, which is a question that only exists on a
    system where it is a path. The Windows spelling has a test of its own.
    """
    if not Path("/srv/repos").is_absolute():
        pytest.skip("`/srv/repos` is not an absolute path on this system, and "
                    "Frontstep refusing it here is the correct behaviour")
