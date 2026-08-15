# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
"""The command line: `init`, `serve`, `adopt`, `skill`, `doctor`.

Five commands and no framework — argparse is in the standard library and this
is not a tool that needs subcommand plugins.

Two of them write outside their own folder, and where they may write is the
whole point:

  * `init` writes the configuration file and ONE example folder, and never
    touches a project the user already has. On a fresh machine there is nothing
    to adopt anyway: the status document is a convention, not a standard, so
    scanning for one finds nothing — and writing one into forty folders on first
    run is how a tool gets uninstalled.
  * `adopt` writes a status document into the folders the user picks, one by
    one, and is never run automatically.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ntpath
import os
import sys
from pathlib import Path

from . import __version__, config as C, core as F, launch as L

ASSETS = Path(__file__).resolve().parent / "assets"

# The folder `init` creates so the dashboard does not open empty. Its status
# document doubles as the tutorial.
EXAMPLE_FOLDER = "frontstep-example"

# Ignored when measuring "when was this project last touched": these change for
# reasons that have nothing to do with the work.
NOT_WORK = {".git", "venv", ".venv", "node_modules", "__pycache__", ".mypy_cache",
            ".pytest_cache", ".ruff_cache", ".tox", "dist", "build", ".idea", ".vscode"}


# ---- saying things on a console that may not take our symbols ---------------
#
# ⚠️ A cp1252 console (Windows) cannot encode `✓`, and printing it raises. Asked
# of the STREAM, not of the platform: a Windows terminal set to UTF-8 keeps the
# real symbols. All replacements are two characters wide — `doctor` prints its
# mark in a column.
ASCII_FOR = {"✓": "ok", "✗": "!!", "·": "--", "→": "->", "⚠️": "!", "⚠": "!"}


def _encodable(text: str, stream) -> bool:
    """Whether this stream can carry this text as it stands."""
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return True                      # it did not say; let it try
    try:
        text.encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def say(*parts, file=None, **kwargs) -> None:
    """`print`, minus whatever this console cannot encode.

    The last resort matters: a path can hold characters no codepage covers, and
    `doctor` must still report on the console that cannot spell them.
    """
    stream = file or sys.stdout
    out = []
    for part in parts:
        text = str(part)
        if not _encodable(text, stream):
            for fancy, plain in ASCII_FOR.items():
                text = text.replace(fancy, plain)
        if not _encodable(text, stream):
            encoding = getattr(stream, "encoding", None) or "utf-8"
            text = text.encode(encoding, "replace").decode(encoding, "replace")
        out.append(text)
    print(*out, file=stream, **kwargs)


def _split_root(raw: str) -> tuple[str, str, list[str]]:
    """`--root PATH`, `PATH:LABEL` or `PATH:LABEL:tag,tag`.

    ⚠️ The PATH can hold a colon of its own: `C:\\Users\\me\\code` split on
    `:` gives a root called `C`. The drive comes off first and goes back after,
    so the split only sees what cannot contain one.
    """
    drive, rest = ntpath.splitdrive(raw)
    parts = rest.split(":")
    label = parts[1] if len(parts) > 1 else ""
    tags = [t for t in (parts[2].split(",") if len(parts) > 2 else []) if t]
    return drive + parts[0], label, tags


# ---- small helpers ---------------------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    """One question. Empty answer takes the default."""
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return answer or default


def _ask_yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = _ask(f"{prompt} ({hint})").lower()
    if not answer:
        return default
    return answer.startswith(("y", "s"))




def _last_touched(folder: Path) -> dt.date | None:
    """When this project was last worked on, measured from the files.

    Not a guess: it is the most recent modification inside the folder, ignoring
    what changes for other reasons (`.git` after a fetch, `venv` after an
    install). Returns None if nothing readable is in there.
    """
    newest = 0.0
    for current, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in NOT_WORK and not d.startswith(".")]
        for name in files:
            try:
                newest = max(newest, (Path(current) / name).stat().st_mtime)
            except OSError:
                continue
    return dt.date.fromtimestamp(newest) if newest else None


def _readme_description(folder: Path) -> str:
    """A description derived from the project's README, if it has one.

    The same derivation the dashboard applies to a status document — it works on
    any Markdown. Empty when there is no prose to take: an empty description is
    honest, an invented one is not.
    """
    for name in ("README.md", "readme.md", "README", "README.rst", "docs/README.md"):
        candidate = folder / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
            return F.derived_description(text.split("\n")[:120])
    return ""


def _candidates(root: F.Root, status_filename: str) -> list[Path]:
    """Folders under a root that have no status document yet."""
    base = Path(root.folder)
    if not base.is_dir():
        return []
    found = []
    for folder in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if (folder / status_filename).exists():
            continue
        if any(f.name.lower() == status_filename.lower()
               for f in folder.iterdir() if f.is_file()):
            continue
        found.append(folder)
    return found


# ---- init ------------------------------------------------------------------

def cmd_init(args) -> int:
    target = Path(args.config).expanduser() if args.config else C.default_path()
    if target.exists() and not args.force:
        say(f"There is already a configuration at {target}.")
        say("Edit that one, or pass --force to start over.")
        return 1

    roots: list[dict] = []
    if args.root:
        # Non-interactive: --root PATH, repeatable, optionally PATH:LABEL:tag,tag
        for raw in args.root:
            path, label, tags = _split_root(raw)
            roots.append({"path": path,
                          "label": label or Path(path).expanduser().name,
                          "tags": tags})
        settings = {"language": args.language, "stale_days": args.stale_days,
                    "port": args.port, "bind": args.bind, "writable": not args.read_only}
    else:
        say("Frontstep — let's find your projects.\n")
        say("Which folders do you keep projects in? One per line, empty line to stop.")
        say("A project is any folder directly inside one of these.\n")
        known_tags: list[str] = []
        while True:
            raw = _ask(f"  folder {len(roots) + 1}" if roots else "  folder")
            if not raw:
                if roots:
                    break
                say("  At least one is needed.")
                continue
            path = Path(raw).expanduser()
            if not path.is_dir():
                say(f"  {path} is not a folder.")
                continue
            label = _ask("  what do you call it", path.name or "Home")
            if known_tags:
                say(f"  tags used so far: {', '.join(known_tags)}")
            raw_tags = _ask("  tags for everything in it (comma separated)")
            tags = [t for t in (C.normalize_tag(t) for t in raw_tags.split(",")) if t]
            for t in tags:
                if t not in known_tags:
                    known_tags.append(t)
            roots.append({"path": str(path), "label": label, "tags": tags})
            say()

        settings = {
            "language": _ask("Language for new status documents (en/it)", "en"),
            "stale_days": int(_ask("After how many days is a project 'quiet'", "7") or 7),
            "port": int(_ask("Port for the dashboard", "9015") or 9015),
            "bind": "127.0.0.1",
            "writable": _ask_yes("May Frontstep write to your status documents?"),
        }

    C.write_file(target, settings, roots)
    say(f"\n✓ {target}")

    # The one file written outside the configuration: an example folder, created
    # by us, whose document is the tutorial. Nothing the user already had is
    # touched. Shared with the setup page — see `core.create_example`.
    example = F.create_example(roots[0]["path"], language=settings["language"])
    if example is None:
        say(f'  {Path(roots[0]["path"]) / F.EXAMPLE_FOLDER} already exists, left alone')
    else:
        say(f"✓ {example}/ — an example project; its document is the tutorial")

    say("\nNothing else of yours was touched: a status document is a convention,")
    say("not a standard, so there was nothing to find on this machine yet.\n")
    say("  frontstep serve                 → http://%s:%s" % (settings["bind"], settings["port"]))
    say("  frontstep skill --install claude|agents   teach your agent to keep them")
    say("  frontstep adopt                 create minimal documents in folders you pick")
    return 0


# ---- doctor ----------------------------------------------------------------
#
# Every line below is something that has actually gone wrong on a real machine,
# not a checklist of what might. A clean Windows 11 install produces most of it:
# the command installed and not on PATH, a dashboard with nothing on it, the
# configuration in a Unix-shaped folder, the terminal button answering 200 and
# opening nothing.
#
# The rule for what belongs here: a check earns its place by having FAILED
# somewhere real. A doctor that lists everything conceivable is read once and
# never again.

def _check_python() -> tuple[str, str, str]:
    version = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info < (3, 11):
        return ("!", f"Python {version}", "Frontstep needs 3.11 or newer.")
    return ("ok", f"Python {version}", "")


def _check_on_path() -> tuple[str, str, str]:
    """Whether `frontstep` can be typed, or only reached through the interpreter.

    pip warns about this while installing and then moves on, leaving an
    application that is installed and cannot be started. It happened on Windows,
    where the scripts folder is very often not on PATH.
    """
    from shutil import which
    if which("frontstep"):
        return ("ok", "the `frontstep` command", "")
    # Where the scripts really are: beside the interpreter on Unix, in a
    # `Scripts` folder next to it on Windows. Getting this wrong prints a path
    # that does not exist, which is worse than printing none.
    scripts = Path(sys.executable).parent
    if os.name == "nt":
        scripts = scripts / "Scripts"
    return ("~", "the `frontstep` command",
            f"not on PATH — add {scripts} to it, or `uv tool update-shell`.")


def _check_config() -> tuple[str, str, str]:
    try:
        cfg = C.load()
    except C.ConfigMissing:
        return ("~", "configuration", f"none yet — `frontstep serve` will ask. "
                                      f"It would go to {C.default_path()}.")
    except C.ConfigInvalid as e:
        return ("!", "configuration", str(e))
    return ("ok", f"configuration ({cfg.path})", "")


def _check_roots() -> list[tuple[str, str, str]]:
    try:
        cfg = C.load()
    except (C.ConfigMissing, C.ConfigInvalid):
        return []
    out = []
    for root in cfg.roots:
        folder = Path(root.folder)
        if not folder.is_dir():
            out.append(("!", f"root {root.label}", f"{folder} is not there any more."))
            continue
        found = F._count_documented(folder)
        out.append(("ok" if found else "~", f"root {root.label} ({folder})",
                    "" if found else "no project in it has a status document yet."))
    return out


def _check_opening() -> list[tuple[str, str, str]]:
    """What the two buttons on a card would open with, named.

    They disappear rather than fail when there is nothing to open with, and a
    button that is missing without explanation is its own kind of bug.
    """
    try:
        cfg = C.load()
    except (C.ConfigMissing, C.ConfigInvalid):
        cfg = C.Config(roots=[])
    if not L.allowed(cfg):
        why = "`launch = false`" if not cfg.launch else f"`bind = {cfg.bind}` is not loopback"
        return [("~", "opening a terminal and an editor", f"off: {why}.")]
    out = []
    for what, found in (("a terminal", L.terminal_for(cfg)),
                        ("an editor", L.editor_for(cfg))):
        setting = what.split()[-1]
        if found is None:
            # `·` and not `✗`, and the distinction is the whole meaning of the
            # exit code. Nothing to open with does not stop Frontstep working:
            # the dashboard runs and those two buttons are simply not on the
            # cards. A machine with no desktop at all — a server, a CI runner —
            # is a perfectly good place to run this, and telling it that it is
            # broken would be false.
            out.append(("~", f"opening {what}",
                        f"nothing found on this machine, so the button will not be "
                        f"there. Set `{setting} = [...]` to name one."))
        else:
            out.append(("ok", f"opening {what}", f"with {found.name}"))
    return out


def _check_port() -> tuple[str, str, str]:
    import socket
    try:
        cfg = C.load()
        port, bind = cfg.port, cfg.bind
    except (C.ConfigMissing, C.ConfigInvalid):
        port, bind = 9015, "127.0.0.1"
    with socket.socket() as s:
        s.settimeout(1)
        taken = s.connect_ex(("127.0.0.1" if bind in ("0.0.0.0", "") else bind, port)) == 0
    if taken:
        return ("~", f"port {port}", "something is already listening — Frontstep "
                                     "may be running, or the port is somebody else's.")
    return ("ok", f"port {port}", "free")


MARKS = {"ok": "✓", "~": "·", "!": "✗"}


def marks(stream=None) -> dict[str, str]:
    """The three marks, in a set this console can carry WHOLE.

    ⚠️ All three or none: `·` IS in cp1252 and `✓` is not, so deciding per
    symbol mixes widths and bends the column.
    """
    fancy = "".join(MARKS.values())
    if _encodable(fancy, stream or sys.stdout):
        return MARKS
    return {key: ASCII_FOR[symbol] for key, symbol in MARKS.items()}


def cmd_doctor(args) -> int:
    """Say what Frontstep found on this machine, and what to do about it.

    Exit code is 1 only for things that STOP it working. A `·` is worth knowing
    and not worth failing over — most first runs have several.
    """

    lines: list[tuple[str, str, str]] = [
        _check_python(), _check_on_path(), _check_config(), _check_port(),
    ]
    lines += _check_roots()
    lines += _check_opening()

    say(f"Frontstep {__version__} on {sys.platform}\n")
    shown = marks()
    width = max(len(what) for _, what, _ in lines)
    broken = 0
    for mark, what, note in lines:
        broken += mark == "!"
        say(f"  {shown[mark]} {what.ljust(width)}  {note}".rstrip())

    say()
    if broken:
        say(f"{broken} thing(s) marked {shown['!']} will stop it working.")
        return 1
    say("Nothing here stops it working.")
    return 0


# ---- serve -----------------------------------------------------------------

def cmd_serve(args) -> int:
    cfg = None
    try:
        cfg = C.load(args.config)
    except C.ConfigMissing:
        # It USED to stop here and name the command that fixes it. It now
        # starts and asks in the page instead, which is the whole point: for an
        # application whose entire interface is a page, refusing to show the
        # page until a terminal has been dealt with is a strange first move.
        #
        # The reasoning behind the old behaviour still holds and is not being
        # thrown away — a dashboard that comes up pointing at some plausible
        # folder looks broken. A page that ASKS where to look is not that.
        pass
    except C.ConfigInvalid as e:
        # A file that exists and says something unusable is a different case,
        # and setup would be the wrong answer: it would offer to write over
        # something somebody has already written.
        say(f"Configuration problem: {e}")
        return 1

    from .web import create_app               # imported here: it pulls in Flask

    app = create_app(cfg)
    host = args.host or (cfg.bind if cfg else "127.0.0.1")
    port = args.port or (cfg.port if cfg else 9015)

    if cfg is None:
        # The key goes on the address because on a first run there is no page
        # to have read it from — and whoever can see this line is whoever
        # started the program. On a machine with more than one account that is
        # the difference between setting Frontstep up and having it set up for
        # you.
        key = app.config["FRONTSTEP_TOKEN"]
        say(f"Frontstep {__version__} — not set up yet.")
        say(f"\n  Open this, and it will ask you where your projects are:\n")
        say(f"    http://{host}:{port}/?key={key}\n")
        say("  The key is in the address because this page decides which")
        say("  folders Frontstep may read and write.")
        app.run(host=host, port=port, debug=args.debug)
        return 0

    say(f"Frontstep {__version__} — http://{host}:{port}")
    say(f"  {len(cfg.roots)} root(s), from {cfg.path}")
    if not cfg.writable:
        # Worth one line: every command that writes is gone from the page, and
        # a missing button with no explanation reads as a bug.
        say("  read-only: `writable = false`, no status document will be written")
    if host not in ("127.0.0.1", "localhost", "::1"):
        # Worth saying out loud rather than in the README only: this app reads
        # and writes inside a home folder and has no authentication at all.
        say("  ⚠️  listening beyond localhost, and Frontstep has no authentication")
        if not cfg.allowed_hosts:
            # The second half of that warning, and the one that turns into a
            # support question if it is left unsaid: reaching the dashboard by
            # any name other than localhost now answers 403 until the name is
            # declared. Better here, next to the address, than discovered later.
            say("     nothing in `allowed_hosts`: it will only answer on "
                  "localhost, whatever it is bound to")
    if cfg.allowed_hosts:
        say(f"  also answering to: {', '.join(cfg.allowed_hosts)}")
    app.run(host=host, port=port, debug=args.debug)
    return 0


# ---- adopt -----------------------------------------------------------------

def cmd_adopt(args) -> int:
    try:
        cfg = C.load(args.config)
    except (C.ConfigMissing, C.ConfigInvalid) as e:
        say(e)
        return 1

    roots = [r for r in cfg.roots if not args.root or r.key == args.root]
    if not roots:
        say(f"No root with key {args.root!r}. Known: "
              + ", ".join(r.key for r in cfg.roots))
        return 1

    found: list[tuple[F.Root, Path]] = []
    for root in roots:
        found += [(root, folder) for folder in _candidates(root, cfg.status_filename)]

    if not found:
        say("Every folder already has a status document.")
        return 0

    say(f"{len(found)} folder(s) without a status document:\n")
    shown_root = None
    for i, (root, folder) in enumerate(found, 1):
        if root.key != shown_root:
            say(f"  {root.label}  ({root.folder})")
            shown_root = root.key
        when = _last_touched(folder)
        say(f"  {i:3}. {folder.name:28}"
              + (f"last touched {when.isoformat()}" if when else "(empty)"))

    if args.dry_run:
        say("\n--dry-run: nothing written.")
        return 0

    if args.all:
        chosen = found
    else:
        say("\nWhich ones? Numbers separated by spaces, `all`, or empty to stop.")
        raw = _ask("  adopt")
        if not raw:
            say("Nothing written.")
            return 0
        if raw.strip().lower() == "all":
            chosen = found
        else:
            picked = set()
            for piece in raw.replace(",", " ").split():
                try:
                    picked.add(int(piece))
                except ValueError:
                    say(f"  {piece!r} is not a number, ignored")
            chosen = [f for i, f in enumerate(found, 1) if i in picked]

    if not chosen:
        say("Nothing written.")
        return 0

    status = args.status or (F.PAUSED if len(chosen) > 10 else F.ACTIVE)
    if status not in F.STATUS_ORDER or status == F.UNDECLARED:
        say(f"Unknown status: {args.status}")
        return 1

    written = 0
    for root, folder in chosen:
        # Only what can be measured gets written. `Next step` stays empty on
        # purpose: it cannot be inferred from files, and inventing it is worse
        # than leaving it blank.
        description = _readme_description(folder)
        when = _last_touched(folder) or dt.date.today()
        result = F.create_project(
            name=folder.name, root=root, description=description,
            today=when, language=cfg.language, require_description=False,
        )
        if "error" in result:
            say(f"  ✗ {folder.name}: {result['error']}")
            continue
        # create_project writes `active`; the status asked for here is applied
        # on top, in the document's own language.
        if status != F.ACTIVE:
            F.set_status(folder.name, root.folder, status, today=when)
        written += 1
        say(f"  ✓ {folder.name}" + ("" if description else "   (no description found)"))

    say(f"\n{written} document(s) written, status {status}.")
    say("Descriptions were taken from each README where there was one to take;")
    say("`Next step` was left empty, because that cannot be inferred.")
    return 0


# ---- skill -----------------------------------------------------------------

# Only `claude` has a fixed destination. AGENTS.md belongs to a project folder,
# so it is worked out from where the command is run (or from --target).
def cmd_skill(args) -> int:
    if args.print or not args.install:
        which = "AGENTS.md" if args.install == "agents" else "SKILL.md"
        say((ASSETS / which).read_text(encoding="utf-8"))
        return 0

    if args.install == "claude":
        if args.target:
            target = Path(args.target).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ASSETS / "SKILL.md").read_text(encoding="utf-8"),
                              encoding="utf-8")
        else:
            target = F.install_claude_skill()
        say(f"✓ {target}")
        say("  Agent Skills format: any tool implementing it can read this.")
        return 0

    # AGENTS.md is a file the project may well already have: ours goes in as a
    # section between markers, and replacing it later only touches that section.
    # The writing itself is `core.write_agents_block`, shared with the checkbox
    # on "New project" — two ways in, one behaviour.
    # ⚠️ `--target` is a FOLDER here and a FILE for `claude`: `AGENTS.md` has a
    # fixed name inside a project, the skill has a fixed path on the machine.
    # Taking `.parent` of whatever arrived wrote one level ABOVE the project.
    if args.target:
        given = Path(args.target).expanduser()
        folder = given.parent if given.name == F.AGENTS_FILE else given
    else:
        folder = Path.cwd()
    target, what = F.write_agents_block(folder)
    say(f"✓ {target}" + ("" if what == "created"
                           else f" — the Frontstep section was {what}"))
    return 0


# ---- entry point -----------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frontstep",
        description="One page with the state of every project you have.")
    parser.add_argument("--version", action="version", version=f"frontstep {__version__}")
    sub = parser.add_subparsers(dest="command")

    common = {"--config": "path to the configuration file"}

    p_init = sub.add_parser("init", help="create the configuration (asks a few questions)")
    p_init.add_argument("--config", help=common["--config"])
    p_init.add_argument("--root", action="append", metavar="PATH[:LABEL[:tags]]",
                        help="declare a root without being asked; repeatable")
    p_init.add_argument("--language", default="en")
    p_init.add_argument("--stale-days", type=int, default=7)
    p_init.add_argument("--port", type=int, default=9015)
    p_init.add_argument("--bind", default="127.0.0.1")
    p_init.add_argument("--read-only", action="store_true",
                        help="a dashboard that never writes to your documents")
    p_init.add_argument("--force", action="store_true", help="overwrite an existing configuration")
    p_init.set_defaults(func=cmd_init)

    p_serve = sub.add_parser("serve", help="run the dashboard")
    p_serve.add_argument("--config", help=common["--config"])
    p_serve.add_argument("--host")
    p_serve.add_argument("--port", type=int)
    p_serve.add_argument("--debug", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_adopt = sub.add_parser(
        "adopt", help="write a minimal status document into folders you pick")
    p_adopt.add_argument("--config", help=common["--config"])
    p_adopt.add_argument("--root", help="only this root, by key")
    p_adopt.add_argument("--all", action="store_true", help="every candidate, without asking")
    p_adopt.add_argument(
        "--status",
        # Every status a document may declare. `undeclared` is a diagnosis the
        # dashboard makes, not a value anybody writes — and it was cutting
        # `done` off the list with it.
        help="one of: " + ", ".join(s for s in F.STATUS_ORDER if s != F.UNDECLARED))
    p_adopt.add_argument("--dry-run", action="store_true", help="list them and write nothing")
    p_adopt.set_defaults(func=cmd_adopt)

    p_skill = sub.add_parser("skill", help="give the convention to your coding agent")
    p_skill.add_argument("--install", choices=("agents", "claude"),
                         help="claude: ~/.claude/skills/ · agents: ./AGENTS.md")
    p_skill.add_argument("--print", action="store_true", help="print it instead of installing")
    p_skill.add_argument(
        "--target",
        help="where to write it: the FOLDER for `agents`, the file path for `claude`")
    p_skill.set_defaults(func=cmd_skill)

    sub.add_parser(
        "doctor",
        help="check what this machine has, and what it is missing",
    ).set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except KeyboardInterrupt:
        say()
        return 130


if __name__ == "__main__":
    sys.exit(main())
