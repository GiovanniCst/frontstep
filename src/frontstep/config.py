# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
"""The configuration: where the projects are and what things are called.

A TOML file, written by hand or by `frontstep init`. No folder and no label is
written in the code: they are data, because the folders of whoever uses
Frontstep are not the ones of whoever wrote it.

It is looked for in this order, and the first one that exists wins:

  1. the path passed explicitly (`--config`)
  2. `$FRONTSTEP_CONFIG`
  3. `./frontstep.toml`, to keep a configuration next to a project
  4. wherever this system keeps configuration — `%APPDATA%` on Windows,
     `~/Library/Application Support` on macOS, `~/.config` elsewhere,
     and `$XDG_CONFIG_HOME` when it is set (see `config_home`)

If none is found **no default configuration is invented**: `ConfigMissing` is
raised and the caller says how to create one. A dashboard that starts up
pointing at some plausible folder looks broken, and that is worse than an error
explaining what to do.
"""
from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .core import Root

FILE_NAME = "config.toml"
LOCAL_FILE_NAME = "frontstep.toml"
PATH_ENV_VAR = "FRONTSTEP_CONFIG"

# A root's key: it ends up in the URL (`/project/<root>/<name>`) and in element
# ids on the page, so no slashes, spaces or accents.
RE_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class ConfigMissing(Exception):
    """No configuration file found."""


class ConfigInvalid(Exception):
    """The file is there but says something that cannot be used.

    The message is aimed at whoever wrote that file by hand: it names the key
    and what was expected, not a traceback.
    """


@dataclass(frozen=True)
class Config:
    roots: list[Root]
    language: str = "en"          # which language new documents are written in
    stale_days: int = 7           # after how many days a project counts as stale
    port: int = 9015
    bind: str = "127.0.0.1"       # what it listens on: local, not 0.0.0.0
    writable: bool = True         # false = read-only dashboard
    status_filename: str = "CURRENT_STATUS.md"
    index_file: str = ""          # optional source for projects without a document
    path: Path | None = None      # where it was read from, for error messages
    known_tags: tuple[str, ...] = field(default_factory=tuple)  # every declared tag, for the UI
    # Host names this dashboard answers to, BEYOND the loopback ones it always
    # accepts. Empty is the right answer for almost everybody: it is only needed
    # when `bind` reaches past localhost and the address in the browser is
    # therefore not a loopback name. See `web.host_allowed`.
    allowed_hosts: tuple[str, ...] = field(default_factory=tuple)
    # May the server open a terminal and an editor on the machine it runs on?
    # ⚠️ `None` means "not said", and is resolved to `writable` below — somebody
    # who asked for a dashboard that does not touch their files did not ask for
    # one that runs programs. It was `True`, which only `from_data` corrected, so
    # a Config built in Python was read-only and still started programs.
    launch: bool | None = None
    # The commands, empty meaning "work it out for this machine"
    # (`launch.detect_terminal` / `detect_editor`). A list, never a string to be
    # split: splitting is a small shell, and a small shell is how a path with a
    # space in it becomes two arguments.
    terminal: tuple[str, ...] = field(default_factory=tuple)
    editor: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.launch is None:
            object.__setattr__(self, "launch", self.writable)   # frozen dataclass


def normalize_tag(raw: str) -> str:
    """A hand-written tag becomes a stable key.

    `Prod`, `prod` and `PROD` are the same tag: without this step the same word
    spelled two ways would become two different filters on the page, which is
    the mistake everyone makes on their second day of use.
    """
    text = (raw or "").strip().strip("`*").lower()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9àáâäãåèéêëìíîïòóôöõùúûüñç.-]", "", text)
    return text.strip("-.")


def _default_label(path: Path) -> str:
    """What a root nobody named is called: the name of its folder.

    ⚠️ Except the home folder, whose `name` is the USER NAME. It would end up in
    the label shown on the page, in the key inside every URL and in element ids:
    that is, in every screenshot shared or saved. `Home` says the same thing
    without saying who you are.
    """
    if path == Path.home():
        return "Home"
    return path.name or str(path)


def _key_from(label: str, path: Path) -> str:
    """A root's key: from its label, when a usable one can be made of it."""
    candidate = normalize_tag(label) or normalize_tag(_default_label(path))
    return candidate if RE_KEY.match(candidate or "") else "home"


def _prefix_from(path: Path) -> str:
    """How the path reads on a card, shortened by the home folder.

    ⚠️ `~` is a UNIX notation. Measured on Windows, where a card said
    `~/Documents/a_local_test/`: nothing on that system uses `~`, no shell there
    expands it, and pasting it anywhere gets you an error. Windows shortens the
    same way but writes it `%USERPROFILE%`.

    The separator follows the system too — a Windows path with forward slashes
    reads like a URL, not like a place on that disk.
    """
    home = Path.home()
    windows = os.name == "nt"
    short, sep = ("%USERPROFILE%", "\\") if windows else ("~", "/")
    try:
        rel = path.relative_to(home)
    except ValueError:
        text = str(path).rstrip("/\\")
        return f"{text}{sep}"
    if str(rel) == ".":
        return f"{short}{sep}"
    return f"{short}{sep}{str(rel).replace(chr(92), sep).replace('/', sep)}{sep}"


def _root_from_data(data: dict, index: int, taken_keys: set[str]) -> Root:
    if not isinstance(data, dict):
        raise ConfigInvalid(f"[[roots]] entry {index + 1}: expected a table.")
    raw = str(data.get("path", "")).strip()
    if not raw:
        raise ConfigInvalid(f"[[roots]] entry {index + 1}: `path` is missing.")

    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ConfigInvalid(
            f"[[roots]] `{raw}`: an absolute path is needed (`~` is fine).")

    label = str(data.get("label", "")).strip() or _default_label(path)
    key = str(data.get("key", "")).strip() or _key_from(label, path)
    if not RE_KEY.match(key):
        raise ConfigInvalid(
            f"[[roots]] `{raw}`: the key `{key}` is not usable — "
            "lowercase letters, digits, dot, dash and underscore.")
    # Two roots with the same key would give one address to two different
    # folders, and "close" would write into the wrong project.
    if key in taken_keys:
        raise ConfigInvalid(
            f"[[roots]] `{raw}`: the key `{key}` already belongs to another root. "
            "Give one of the two an explicit `key`.")
    taken_keys.add(key)

    raw_tags = data.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    if not isinstance(raw_tags, list):
        raise ConfigInvalid(f"[[roots]] `{raw}`: `tags` wants a list.")
    tags = tuple(dict.fromkeys(t for t in (normalize_tag(str(g)) for g in raw_tags) if t))

    # The HOST path: the same as the first one, except in a container, where the
    # folder is mounted elsewhere and what gets copied has to be the real path on
    # the machine of whoever is looking.
    host = Path(str(data.get("host_path", "")).strip() or path).expanduser()

    return Root(
        key=key,
        folder=str(path),
        host=str(host),
        label=label,
        tags=tags,
        # ⚠️ From the HOST path: this is the address written on the card, and in
        # a container the path Frontstep reads (`/projects/…`) is the one the
        # person looking at it cannot use.
        prefix=_prefix_from(host),
    )


def host_only(raw: str) -> str:
    """The host part of a `Host:` header or of a hand-written allowed host.

    Used on BOTH sides of the comparison in `web.host_allowed`, which is the
    whole reason it lives here and not in one of the two: a host normalized one
    way on the left and another way on the right compares unequal, and the
    dashboard would refuse the browser that is actually looking at it.

    The port goes: it is not part of the identity of a host, and a container
    publishes on a different one than it listens on. IPv6 keeps its colons —
    `[::1]:9015` is the bracketed form, `::1` the bare one, and both come back
    as `::1`.
    """
    text = (raw or "").strip().lower().rstrip(".")
    if text.startswith("["):                       # [::1]:9015 → ::1
        return text[1:].split("]", 1)[0]
    if text.count(":") == 1:                       # localhost:9015 → localhost
        head, _, tail = text.partition(":")
        return head if tail.isdigit() else text
    return text                                    # bare IPv6, or no port at all


def _host_list(raw: list, where: str) -> tuple[str, ...]:
    """Hand-written host names, normalized. Raises on something that is a URL.

    Refusing `http://box.lan` rather than quietly never matching it: a host that
    silently never matches is a dashboard that refuses to write and does not say
    why, which is the failure this whole check exists to avoid inflicting.
    """
    out: list[str] = []
    for item in raw:
        text = str(item).strip()
        if not text:
            continue
        if "/" in text or " " in text:
            raise ConfigInvalid(
                f"`{where}`: `{text}` is not a host name — it wants `box.lan`, "
                "not a URL and not a path.")
        host = host_only(text)
        if host and host not in out:
            out.append(host)
    return tuple(out)


def _argv(value, where: str) -> tuple[str, ...]:
    """A command, as a list of arguments already separated.

    A STRING with a space in it is refused rather than split. Splitting it would
    be a small shell — and a small shell is exactly how `C:\\Program Files\\…`
    becomes two arguments and the command fails with a message about a file
    called `C:\\Program`. The error says what to write instead.
    """
    if value in (None, "", []):
        return ()
    if isinstance(value, str):
        if " " in value.strip():
            raise ConfigInvalid(
                f"`{where}`: write the command as a list, one argument per item "
                f"— {_as_list_example(value)} — not as one string. Arguments are "
                "not split here, so a path with a space in it stays one path.")
        return (value.strip(),)
    if not isinstance(value, list):
        raise ConfigInvalid(f"`{where}`: expected a list of arguments.")
    out = tuple(str(a) for a in value if str(a).strip() != "")
    if not out:
        return ()
    return out


def _as_list_example(value: str) -> str:
    return "[" + ", ".join(f'"{p}"' for p in value.split()) + "]"


def _boolean(value, where: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigInvalid(f"`{where}`: expected true or false.")


def _integer(value, where: str, lowest: int, highest: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ConfigInvalid(f"`{where}`: expected a number.") from None
    if not lowest <= n <= highest:
        raise ConfigInvalid(f"`{where}`: must be between {lowest} and {highest}.")
    return n


def from_data(data: dict, path: Path | None = None) -> Config:
    """A Config from an already parsed dictionary. Kept apart from `load`
    because this is the part that can be tested without writing files."""
    raw_roots = data.get("roots", [])
    if not isinstance(raw_roots, list) or not raw_roots:
        raise ConfigInvalid(
            "At least one root is needed: a `[[roots]]` table with a `path`.")

    keys: set[str] = set()
    roots = [_root_from_data(r, i, keys) for i, r in enumerate(raw_roots)]

    language = str(data.get("language", "en")).strip().lower() or "en"
    status_filename = str(data.get("status_file", "CURRENT_STATUS.md")).strip() or "CURRENT_STATUS.md"
    if "/" in status_filename or "\\" in status_filename:
        raise ConfigInvalid("`status_file`: that is a file name, not a path.")

    # The tags of every root, in the order they appear: the page uses them to
    # know which filters exist even before reading a single document.
    known: list[str] = []
    for r in roots:
        known += [t for t in r.tags if t not in known]

    raw_hosts = data.get("allowed_hosts", [])
    if isinstance(raw_hosts, str):
        raw_hosts = [raw_hosts]
    if not isinstance(raw_hosts, list):
        raise ConfigInvalid("`allowed_hosts`: wants a list of host names.")
    allowed_hosts = _host_list(raw_hosts, "allowed_hosts")

    writable = _boolean(data.get("writable", True), "writable")

    return Config(
        roots=roots,
        language=language,
        stale_days=_integer(data.get("stale_days", 7), "stale_days", 1, 365),
        port=_integer(data.get("port", 9015), "port", 1, 65535),
        bind=str(data.get("bind", "127.0.0.1")).strip() or "127.0.0.1",
        writable=writable,
        status_filename=status_filename,
        index_file=str(data.get("index_file", "")).strip(),
        path=path,
        known_tags=tuple(known),
        allowed_hosts=allowed_hosts,
        launch=_boolean(data["launch"], "launch") if "launch" in data else None,
        terminal=_argv(data.get("terminal"), "terminal"),
        editor=_argv(data.get("editor"), "editor"),
    )


# ---- writing one --------------------------------------------------------
#
# Here rather than in the CLI because there are two ways in now: `frontstep
# init` asks its questions in a terminal, and the browser asks the same ones on
# a first run. One writer for both, or the two files drift and the one nobody
# uses drifts first.

def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_file(path: Path, settings: dict, roots: list[dict]) -> None:
    """Write the configuration as TOML, by hand.

    By hand because it is a dozen lines and this way it comes out commented and
    in the order a human reads it, which a serialiser cannot do — and the file
    is meant to be edited afterwards. Python has no TOML writer in the standard
    library anyway.

    ⚠️ Top-level keys go BEFORE the first `[[roots]]`, and that is not a style
    choice: in TOML every key after a table header belongs to that table, so a
    `port` written below would silently become a root's port and the real one
    would stay at its default. Easy to do by hand, and it happened once here.
    """
    lines = [
        "# Frontstep configuration.",
        "# Written by Frontstep, meant to be edited by hand afterwards.",
        "",
        f"language = {_toml_string(settings['language'])}    # language used for NEW documents",
        f"stale_days = {settings['stale_days']}    # after how many days a project counts as quiet",
        f"port = {settings['port']}",
        f"bind = {_toml_string(settings['bind'])}    # localhost: this app has no authentication",
        f"writable = {'true' if settings['writable'] else 'false'}"
        "    # false = read-only dashboard",
        "",
        "# Frontstep asks your system to open the terminal and the editor you have",
        "# already chosen. Name them here to override that — a LIST, one",
        "# argument per item: `{}` is the project folder, `{file}` its document.",
        '#   terminal = ["kitty", "--directory", "{}"]',
        '#   editor   = ["subl", "{}"]',
        "#   launch   = false        # do not open anything at all",
        "",
    ]
    for root in roots:
        lines.append("[[roots]]")
        lines.append(f"path = {_toml_string(root['path'])}")
        lines.append(f"label = {_toml_string(root['label'])}")
        if root.get("tags"):
            inside = ", ".join(_toml_string(t) for t in root["tags"])
            lines.append(f"tags = [{inside}]")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def candidate_paths(explicit: str | Path | None = None) -> list[Path]:
    """The places the configuration is looked for, in order."""
    if explicit:
        return [Path(explicit).expanduser()]

    candidates = []
    from_env = os.environ.get(PATH_ENV_VAR, "").strip()
    if from_env:
        candidates.append(Path(from_env).expanduser())
    candidates.append(Path.cwd() / LOCAL_FILE_NAME)
    candidates.append(default_path())
    return candidates


def config_home() -> Path:
    """The folder this system keeps a program's configuration in.

    Not the same answer everywhere, and getting it wrong is not fatal — it just
    puts a file where nobody on that system would look for it. Measured on a
    clean Windows 11: Frontstep created `C:\\Users\\…\\.config\\frontstep\\`, a
    dot-folder in the home directory, which is a Unix convention and a place no
    other Windows program writes to.

    `XDG_CONFIG_HOME` still wins where it is set, because somebody who has set
    it has said where they want this.
    """
    if (xdg := os.environ.get("XDG_CONFIG_HOME", "").strip()):
        return Path(xdg).expanduser()
    if os.name == "nt":
        # %APPDATA% is where Windows programs keep settings that follow the user
        # between machines. It is always set on Windows; the fallback is only
        # for the case where something has unset it.
        if (appdata := os.environ.get("APPDATA", "").strip()):
            return Path(appdata)
        return Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".config"


def default_path() -> Path:
    """Where Frontstep writes the configuration unless told otherwise."""
    return config_home() / "frontstep" / FILE_NAME


def _from_env(cfg: Config) -> Config:
    """Environment variables win over the file.

    They serve a container, which may not have the configuration file mounted:
    the same keys are passed as `FRONTSTEP_PORT`, `FRONTSTEP_BIND` and so on.
    The ROOTS are not among them: those stay in the file, because they are a
    structure, and squeezing a structure into an environment variable is how you
    get it wrong.
    """
    changes: dict = {}
    if (v := os.environ.get("FRONTSTEP_PORT", "").strip()):
        changes["port"] = _integer(v, "FRONTSTEP_PORT", 1, 65535)
    if (v := os.environ.get("FRONTSTEP_BIND", "").strip()):
        changes["bind"] = v
    if (v := os.environ.get("FRONTSTEP_STALE_DAYS", "").strip()):
        changes["stale_days"] = _integer(v, "FRONTSTEP_STALE_DAYS", 1, 365)
    if (v := os.environ.get("FRONTSTEP_LANGUAGE", "").strip()):
        changes["language"] = v.lower()
    if (v := os.environ.get("FRONTSTEP_WRITABLE", "").strip()):
        changes["writable"] = v.lower() in ("1", "true", "yes", "on")
    if (v := os.environ.get("FRONTSTEP_LAUNCH", "").strip()):
        changes["launch"] = v.lower() in ("1", "true", "yes", "on")
    if (v := os.environ.get("FRONTSTEP_ALLOWED_HOSTS", "").strip()):
        # Comma separated, unlike the roots: this one IS a flat list of names,
        # not a structure, so an environment variable holds it without lying.
        changes["allowed_hosts"] = _host_list(v.split(","), "FRONTSTEP_ALLOWED_HOSTS")
    if not changes:
        return cfg
    return Config(**{**cfg.__dict__, **changes})


def load(explicit: str | Path | None = None) -> Config:
    """The configuration, from the first file found. Raises if there is none."""
    tried = candidate_paths(explicit)
    for path in tried:
        if not path.is_file():
            continue
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigInvalid(f"{path}: invalid TOML — {e}") from None
        except OSError as e:
            raise ConfigInvalid(f"{path}: cannot read it — {e}") from None
        return _from_env(from_data(data, path))

    raise ConfigMissing(
        "No configuration found. Looked in:\n  "
        + "\n  ".join(str(p) for p in tried)
    )
