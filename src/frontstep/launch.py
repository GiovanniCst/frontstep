# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
"""Opening a terminal and an editor on the machine the dashboard runs on.

A page served over `http://` cannot start a program: that is a barrier the
browser puts there on purpose, and no amount of markup gets around it. It is
why the Terminal button used to go through a protocol handler the user had to
register by hand, and why Editor was a `vscode://` link that did nothing at all
on a machine without a VS Code family editor — silently, which is worse.

But the server runs on the SAME MACHINE as whoever is looking. What the browser
may not do, the process serving it may. So the buttons ask the server, and the
server opens the thing.

That trade is not free, and the price is paid elsewhere: the routes that reach
this module are the ones behind the `Host` check and the page token in `web.py`.
Read that comment before touching this file — a dashboard that runs programs
and answers any caller is a remote shell with a nice stylesheet.

What keeps THIS module safe is narrower, and it is the same shape as the rule
`_apply_to_header` follows for writes: **nothing from the network ever becomes
part of a command.** A route passes a root key and a project name, both of which
have already been resolved against the configured roots; the path that comes out
is placed into an argv LIST as one element, and there is no shell anywhere to
re-split it. A project called `; rm -rf ~` is a folder with a silly name, not a
command — it cannot be, because no string is ever parsed.
"""
from __future__ import annotations

import ntpath
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Where the path goes in a command. Both are matched by EQUALITY against whole
# argv elements, never substituted into a string, so a path is never able to
# become more than the one argument it is, however it is spelled.
SLOT = "{}"              # the project folder
SLOT_FILE = "{file}"     # its status document

# The names that DESCRIBE what is about to open instead of naming a program.
# They are the interesting half of the point — Frontstep asks the system for
# whatever the user already chose, so there is no program to name — and they end
# up in the tooltip of a button, which makes them interface: the page runs them
# through `t()`, and `DESCRIBED_NAMES` is what tells the test suite these three
# are asked for by variable. Everything else a Launcher can be called is a
# program somebody installed (`kitty`, `wt.exe`) or an application's own name
# (`Terminal`), and those stay exactly as they are in every language.
DEFAULT_WINDOWS_TERMINAL = "the default Windows terminal"
PROGRAM_FOR_MD = "the program Windows opens .md with"
DEFAULT_TEXT_EDITOR = "the default text editor"
DESCRIBED_NAMES = (DEFAULT_WINDOWS_TERMINAL, PROGRAM_FOR_MD, DEFAULT_TEXT_EDITOR)


def holds(argv, slot: str) -> bool:
    """Whether this command carries that placeholder anywhere.

    Anywhere, not as an element of its own: a flag may take the path with an
    equals sign (`--working-directory={}`), and asking `slot in argv` says no to
    exactly those — which is how three of the six Linux terminals ended up
    running with a folder called `{}`.
    """
    return any(slot in part for part in argv)


@dataclass(frozen=True)
class Launcher:
    """One way of opening something, and what it wants to be given."""
    name: str                      # what to call it when the page has to say
    argv: tuple[str, ...]          # the command, with SLOT where the path goes
    wants: str = "folder"          # "folder" — the project; "file" — its document
    windows_path: bool = False     # convert to a Windows path first (WSL)
    # ⚠️ The two below are WINDOWS ONLY, and they exist because a real Windows
    # machine proved that going through a shell there does not work. Measured on
    # a clean Windows 11: `cmd.exe /c start "" /D <folder> cmd.exe` opens a
    # terminal when TYPED, and opens nothing at all when the same list is handed
    # to `subprocess.Popen` — while `Popen` reports success, because `cmd.exe`
    # did start. The route answered 200 and the user got nothing.
    new_console: bool = False      # give it a console of its own (CREATE_NEW_CONSOLE)
    shell_open: bool = False       # hand it to the shell, the way a double-click does


def in_wsl() -> bool:
    """Whether this Linux is Linux inside Windows.

    It matters more than it looks: the terminal and the editor a WSL user wants
    are WINDOWS programs, reached through the interop layer, and they want a
    Windows path. Getting this wrong does not fail loudly — it opens a terminal
    nobody can see, or none at all.
    """
    if platform.system() != "Linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


@lru_cache(maxsize=None)
def _which(*names: str) -> str:
    """The first of these programs that is actually installed. "" if none is.

    Asking the system instead of assuming is the entire point of this file: the
    old Editor button assumed VS Code and had nothing to say when it was wrong.

    Cached because on WSL it is not cheap — looking for `wt.exe` walks the
    Windows PATH across `/mnt/c`, and the answer cannot change while the process
    runs. Measured: it took the test suite from 1s to 11s before this. Tests
    that move PATH around call `_which.cache_clear()`.
    """
    for name in names:
        if (found := shutil.which(name)):
            return found
    return ""


def windows_path(path: str) -> str:
    """A WSL path as Windows sees it. The path unchanged if it cannot be told.

    `wslpath` ships with WSL itself, so this is not a dependency anybody has to
    install. If it ever fails, handing the Linux path over is better than
    refusing: some programs take it, and the ones that do not fail visibly.
    """
    try:
        done = subprocess.run(["wslpath", "-w", path], capture_output=True,
                              text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return path
    return done.stdout.strip() or path


# ---- what to open a terminal with ------------------------------------------
#
# The rule is the same as for the editor: ASK THE SYSTEM FOR ITS OWN. Windows
# has a "default terminal application" setting and `start` honours it; Debian
# and its derivatives have `x-terminal-emulator`, which is that same question in
# symlink form. Neither names a program, so neither can name the wrong one.
#
# `wt.exe` is never called directly, and that is measured rather than a matter
# of taste. Four failures, each found by opening a real window and looking at
# it: `-d` starts the DEFAULT PROFILE, so a Windows path landed on
# `\\wsl.localhost\...` which PowerShell refuses (0x8007010b) while a Linux path
# meant nothing to it; `wt.exe` rejoins its arguments and parses them again, so
# `wt.exe wsl.exe --cd <path>` had the `--cd` swallowed; naming `wsl.exe` after
# `-d` still produced a PowerShell window on a machine whose default profile is
# a WSL one; and it asked for a permission every single time. Going through
# `start` gets Windows Terminal anyway, if that is what the user has chosen.

def has_display() -> bool:
    """Whether a window opened here would be visible to anybody.

    On WSL this is WSLg, and it is the difference between a terminal appearing
    on the desktop and a process starting where nobody can see it.
    """
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


# The terminals a Linux desktop installs with itself, in the order they are
# tried, each with the way IT spells "start here". A tuple rather than a literal
# inside the function so the tests can walk every row: the flag of a terminal
# nobody here runs is exactly the thing that rots unnoticed.
#
# ⚠️ `ptyxis` and `kgx` were added on 15/08/2026 after installing Frontstep on a
# Fedora live image: neither was in this list, `gnome-terminal` was not on the
# machine, and `doctor` announced "nothing found on this machine" from inside a
# perfectly good terminal. Fedora Workstation ships Ptyxis; GNOME Console (kgx)
# is what it shipped before. Both flags come from their own documentation —
# `ptyxis --help` on that machine, and the kgx(1) manual page — and the ptyxis
# one was then watched opening a window in /etc, because an option that parses
# is not the same fact as a window that appears where it should.
LINUX_TERMINALS = (
    ("x-terminal-emulator", ()),          # the system's own choice; inherits cwd
    ("ptyxis", ("--new-window", "-d", SLOT)),
    ("kgx", ("--working-directory=" + SLOT,)),
    ("gnome-terminal", ("--working-directory=" + SLOT,)),
    ("konsole", ("--workdir", SLOT)),
    ("xfce4-terminal", ("--working-directory=" + SLOT,)),
    ("mate-terminal", ("--working-directory=" + SLOT,)),
    ("xterm", ()),                        # inherits cwd, and is everywhere
)


def _linux_terminal() -> Launcher | None:
    """The terminal this Linux came with.

    `x-terminal-emulator` comes first because it is not a program: it is the
    system's own answer to "the terminal", set by the distribution and
    changeable by whoever uses it. Asking it beats guessing. The rest are the
    terminals a desktop environment installs with itself, and `xterm` is the
    last resort that has been on X11 systems for forty years.

    Terminals people install for themselves — kitty, alacritty, wezterm — are
    deliberately NOT here. Defaulting to one would be picking somebody's editor
    war for them, and anyone who has installed one can name it in two lines of
    configuration.

    Each spells "start here" its own way, which is why the flag is part of the
    command rather than a shared argument: `cwd=` would be tidier, but
    gnome-terminal hands the job to a server process and ignores it.
    """
    for program, args in LINUX_TERMINALS:
        if _which(program):
            # No SLOT means it takes the working directory it is started in,
            # which `run()` sets. Appending a path would make it a command.
            return Launcher(program, (program,) + args)
    return None


def detect_terminal() -> Launcher | None:
    system = platform.system()

    if in_wsl():
        # `start` opens a console, and WHICH console is the user's own setting —
        # "Default terminal application" on Windows 11, which is how somebody
        # who uses Windows Terminal gets Windows Terminal without Frontstep
        # naming it. `wsl.exe --cd` puts the shell in the project's folder using
        # the Linux path, so nothing has to be translated.
        #
        # A Linux terminal drawn by WSLg is NOT the default here, and it is a
        # near miss rather than an oversight: it needs WSLg, and it needs a
        # terminal emulator installed inside the distribution, neither of which
        # is true of a fresh WSL. Worse, where one IS installed it may well have
        # arrived as another package's dependency and never been chosen by
        # anybody — so preferring it would be picking a program the user does
        # not use. `cmd.exe` and `wsl.exe` are there by definition if WSL is
        # what you are running.
        return Launcher(DEFAULT_WINDOWS_TERMINAL,
                        ("cmd.exe", "/c", "start", "", "wsl.exe", "--cd", SLOT))

    if system == "Windows":
        # No shell, and no `start`. A console process launched with
        # CREATE_NEW_CONSOLE is hosted by the user's DEFAULT TERMINAL
        # APPLICATION — the same Windows setting `start` honours — so the
        # principle survives while the shell that could not deliver it goes.
        # The folder arrives through `cwd`, which is how a process is told where
        # to be born, rather than through a flag a shell has to re-parse.
        return Launcher(DEFAULT_WINDOWS_TERMINAL, ("cmd.exe",),
                        new_console=True)

    if system == "Darwin":
        # `open -a Terminal <folder>` is the documented way and needs nothing
        # installed: Terminal.app is part of macOS.
        return Launcher("Terminal", ("open", "-a", "Terminal", SLOT))

    return _linux_terminal()


# ---- what to open an editor with -------------------------------------------
#
# NOT an editor Frontstep picked. Every system has a way of being asked "open
# this file with whatever the person who uses me has chosen for it", and that
# is what these commands are: `xdg-open` on Linux, `open -t` on macOS, `start`
# on Windows. The answer is a choice the user already made, years ago, in their
# own settings — nothing to install, nothing to configure, and nobody excluded.
#
# It is also strictly better than naming the program a system ships with.
# Plenty of machines have `.md` registered to something other than Notepad, and
# on those, opening Notepad would override a choice the user had already made —
# which is the same mistake as hard-coding `vscode://`, one size down.
#
# So no editor is DETECTED at all, and that is the design. There is no list of
# favourites to keep up to date and no argument about whose editor goes first.
#
# All of these are handed the status DOCUMENT, not the folder: it is a file
# association that answers, and a folder is not a file. A project editor wants
# the folder, and `{}` in the configuration is how to ask for that instead.

def detect_editor() -> Launcher | None:
    system = platform.system()

    if system == "Windows":
        # `os.startfile` IS the double-click: the same shell verb `start` runs,
        # reached through the Windows API instead of through a command line that
        # has to be quoted, passed to a shell, and parsed again. Nothing to
        # escape, so nothing to get wrong.
        return Launcher(PROGRAM_FOR_MD, (SLOT_FILE,),
                        wants="file", shell_open=True)

    if in_wsl():
        # From WSL the API above is not reachable — this is Linux — so the shell
        # verb is invoked through the interop layer instead. Measured working on
        # a real WSL, including on a folder whose name has a space in it. The
        # empty string is not decoration: `start`'s first quoted argument is the
        # window TITLE, so without it a quoted path would be swallowed as one.
        return Launcher(PROGRAM_FOR_MD,
                        ("cmd.exe", "/c", "start", "", SLOT_FILE),
                        wants="file", windows_path=True)

    if system == "Darwin":
        # `-t` means "the default TEXT editor" — TextEdit unless the person has
        # chosen otherwise, in which case it is what they chose.
        return Launcher(DEFAULT_TEXT_EDITOR, ("open", "-t", SLOT_FILE),
                        wants="file")

    if _which("xdg-open"):
        return Launcher(DEFAULT_TEXT_EDITOR, ("xdg-open", SLOT_FILE),
                        wants="file")

    # A machine with no desktop at all. `$VISUAL` and `$EDITOR` are terminal
    # editors: starting one from a web server would open it where nobody can
    # see it, so saying there is none is the honest answer.
    return None


def from_config(argv: tuple[str, ...] | list) -> Launcher | None:
    """A command written by hand in the configuration file.

    Two placeholders, because the two useful things to be handed are not the
    same thing: `{}` is the project FOLDER — what a project editor wants — and
    `{file}` is its status document, which is what an editor that opens one file
    at a time wants. Writing `{file}` is how you say so; there is no second
    setting to keep in step with this one.

    A command with neither is given the folder appended, because that is what
    somebody who wrote `editor = ["kate"]` meant, and refusing it over a missing
    placeholder would be pedantry aimed at the person the setting exists for.
    """
    argv = tuple(str(a) for a in argv if str(a).strip() != "")
    if not argv:
        return None
    wants = "file" if holds(argv, SLOT_FILE) else "folder"
    if not holds(argv, SLOT) and not holds(argv, SLOT_FILE):
        argv += (SLOT,)
    return Launcher(argv[0], argv, wants=wants)


def build(launcher: Launcher, folder: str, document: str) -> list[str]:
    """The command as it will actually be run, path already in place.

    Substitution happens INSIDE one argv element and never across two: an element
    holding a placeholder comes out as one element with the path in it. That is
    the property that matters — no string is ever handed to a shell to be split
    again, so a path cannot become more than the single argument it is, whatever
    it contains.

    ⚠️ It used to require the element to BE the placeholder, which quietly broke
    every terminal whose flag takes the path with an `=`:
    `gnome-terminal --working-directory={}` was passed through untouched and
    started in a folder literally called `{}`. Found on Fedora, in the same
    session that found `ptyxis` missing from the list — nobody had run this on a
    Linux desktop before.
    """
    def swap(part: str) -> str:
        for slot, value in ((SLOT, folder), (SLOT_FILE, document)):
            if slot in part:
                path = windows_path(value) if launcher.windows_path else value
                return part.replace(slot, path)
        return part

    return [swap(part) for part in launcher.argv]


# ---- what the configuration and the routes agree on -------------------------

# `bind` values that mean "only this machine". Opening programs is tied to them
# and not only to the `launch` flag: a dashboard reachable from the network that
# starts a terminal on the machine it runs on is a remote shell, whatever the
# person who set `bind` had in mind. In a container the question does not even
# arise — there is no terminal in there to open — so nothing is lost.
LOOPBACK_BINDS = ("127.0.0.1", "localhost", "::1", "")


def allowed(cfg) -> bool:
    """Whether this configuration may open anything at all."""
    return bool(cfg.launch) and cfg.bind in LOOPBACK_BINDS


def terminal_for(cfg) -> Launcher | None:
    """The terminal this configuration opens with, or None if it opens none."""
    if not allowed(cfg):
        return None
    return from_config(cfg.terminal) or detect_terminal()


def editor_for(cfg) -> Launcher | None:
    """The editor this configuration opens with, or None if it opens none."""
    if not allowed(cfg):
        return None
    return from_config(cfg.editor) or detect_editor()


def _inherits_directory(launcher: Launcher) -> bool:
    """Whether this command is told where to start by being STARTED there.

    True only when neither placeholder is in its argv — `xterm` and
    `x-terminal-emulator` take no directory argument and take the one they are
    given. For every other command the path is already an argument.
    """
    return not holds(launcher.argv, SLOT) and not holds(launcher.argv, SLOT_FILE)


class LaunchFailed(Exception):
    """The command could not be started — usually because it is not installed."""


def run(launcher: Launcher, folder: str, document: str) -> list[str]:
    """Start it, and do not wait for it. Returns the command that was run.

    Whatever it is started with, it outlives the request that opened it and its
    streams go nowhere: a terminal that dies with the response, or that fills
    the server's log with its own output, is not a terminal anybody wanted.

    Only the failure that CAN be told apart is reported: a command that is not
    there raises immediately. Whether a WINDOW appeared is not knowable from
    here, and that gap is not academic — on Windows it is exactly what made the
    button answer 200 and do nothing.
    """
    argv = build(launcher, folder, document)

    # ⚠️ The one place where "argv is a list, so nothing is parsed" stops being
    # true: under WSL the argv goes to `cmd.exe`, and the interop layer rebuilds
    # a Windows command line that cmd parses again. A `"` in a folder name closes
    # the quoting and what follows becomes a second command — measured. That
    # character is legal in a POSIX name and forbidden in a Windows one, so
    # refusing it here costs nothing that works today.
    if argv and ntpath.basename(argv[0]).lower() == "cmd.exe" \
            and any('"' in part for part in argv[1:]):
        raise LaunchFailed(
            'that path contains a `"`, which cannot be passed through cmd.exe '
            "safely. Rename the folder, or open it yourself.")

    # The shell verb, on Windows, through the API instead of a command line.
    # `os.startfile` exists only there, which is the point: it is the same thing
    # a double-click does, with nothing to quote and nothing to re-parse.
    if launcher.shell_open:
        try:
            os.startfile(argv[-1])              # noqa: S606 — Windows only
        except (OSError, AttributeError, ValueError) as e:
            raise LaunchFailed(f"{launcher.name} could not be started: {e}") from None
        return argv

    # Streams sent nowhere, so a terminal cannot fill the server's log with its
    # own output — EXCEPT when it has a console of its own, where the streams
    # belong to that console.
    #
    # ⚠️ Measured, and it is not a nicety: `cmd.exe` READS from standard input.
    # Handed DEVNULL it sees end-of-input immediately and exits, so the window
    # opened and vanished in the same instant. The redirection that protects the
    # log kills the very thing the button exists to open.
    extra: dict = {} if launcher.new_console else {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if launcher.new_console:
        # ⚠️ CREATE_NEW_CONSOLE, and not `start_new_session`. That one is
        # POSIX-only and Windows ignores it in silence, which is how a console
        # program ended up inheriting the server's console instead of getting
        # one of its own — and then not appearing at all. A process started this
        # way is hosted by the user's DEFAULT TERMINAL APPLICATION, so the
        # principle "open the terminal they chose" survives the fix.
        extra["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    elif os.name == "posix":
        extra["start_new_session"] = True

    try:
        subprocess.Popen(                       # noqa: S603 — a list, never a shell
            argv,
            # For `new_console` it is the ONLY way the program is told where to
            # start, and the same goes for `xterm` and `x-terminal-emulator`,
            # which take no directory argument. Everything else already carries
            # the path in its argv, and setting it anyway does harm — measured:
            # a Windows program started from a WSL folder gets a
            # `\\wsl.localhost\…` working directory, which `cmd.exe` refuses
            # outright before it ever looks at its arguments.
            cwd=folder if _inherits_directory(launcher) and os.path.isdir(folder) else None,
            **extra,
        )
    except (OSError, ValueError) as e:
        raise LaunchFailed(f"{launcher.name} could not be started: {e}") from None
    return argv
