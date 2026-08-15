"""Opening a terminal and an editor: what gets run, and what cannot get run.

This is the module that turned Frontstep into a program that starts programs, so
the tests here are weighted towards the second half of that sentence. The ones
that matter most are not "does it open a terminal" — that needs a desktop and a
person to look at it — but "can anything that arrives over HTTP change the
command", and the answer has to stay no.

The defence is the same shape as the one `_apply_to_header` uses for writes: not
a check on the text, but a design in which the text never reaches a place where
it could be parsed. So these tests do not look for escaping. They look for the
path arriving as ONE argv element, whatever it is called.
"""
import os
from pathlib import Path

import pytest

from conftest import ANY_ABSOLUTE, can_be_a_folder_name

from frontstep import config as C, core as F, launch as L
from frontstep.web import create_app

DOCUMENT = """# Project

**Status:** active
**Updated:** 2026-01-05
**Next step:** Read §4 again
**Waiting for:**
**Description:** A project used to check what gets run
"""


def _root(tmp_path: Path, name: str = "prog") -> Path:
    root = tmp_path / "projects"
    (root / name).mkdir(parents=True)
    (root / name / "CURRENT_STATUS.md").write_text(DOCUMENT, encoding="utf-8")
    return root


def _app(tmp_path: Path, **extra):
    root = _root(tmp_path, extra.pop("project", "prog"))
    cfg = C.Config(
        roots=[F.Root(key="projects", folder=str(root), host=str(root),
                      prefix="~/projects/", label="Projects", tags=())],
        **extra,
    )
    app = create_app(cfg)
    client = app.test_client()
    client.environ_base["HTTP_X_FRONTSTEP_TOKEN"] = app.config["FRONTSTEP_TOKEN"]
    return client, root


@pytest.fixture
def ran(monkeypatch):
    """Captures the argv instead of starting anything."""
    seen = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            seen.append((list(argv), kwargs))

    monkeypatch.setattr(L.subprocess, "Popen", FakePopen)
    return seen


# ---- nothing from the network becomes part of a command --------------------

@pytest.mark.parametrize("folder", [
    "a project with spaces",
    "prog; rm -rf ~",
    "prog && shutdown",
    "prog$(whoami)",
    "prog`id`",
    "prog|tee",
    'prog"quoted"',
])
def test_a_project_name_stays_one_argument(tmp_path, ran, monkeypatch, folder):
    """The names here are folder names, not attacks — a folder may be called
    anything the filesystem allows, and `; rm -rf ~` is allowed.

    They cannot become commands because nothing is ever parsed: the path is one
    element of a list handed to a process, and there is no shell to re-split it.
    That is what this asserts — not that the characters were escaped, which
    would mean somebody was still parsing.

    "Anything the filesystem allows" is the operative phrase, and it is not the
    same set everywhere: `|` and `"` are ordinary characters in a POSIX name and
    forbidden in a Windows one, where the folder cannot be created to begin
    with. Asked of the filesystem rather than assumed either way.
    """
    if not can_be_a_folder_name(tmp_path, folder):
        pytest.skip(f"this filesystem will not have a folder called {folder!r}, "
                    "so there is no such name to keep in one piece")
    monkeypatch.setattr(L, "detect_terminal",
                        lambda: L.Launcher("term", ("term", "-d", L.SLOT)))
    client, root = _app(tmp_path, project=folder)

    r = client.post(f"/project/projects/{folder}/open/terminal")

    assert r.status_code == 200
    argv, _ = ran[0]
    assert argv == ["term", "-d", str(root / folder)]     # exactly three, always


@pytest.mark.parametrize("name", ["../elsewhere", "a/b", "a\\b", ".hidden"])
def test_a_name_that_is_a_path_never_reaches_a_command(tmp_path, ran, name):
    """The earlier half of the same defence, and it was already there: a project
    is looked up as a DIRECT CHILD of a declared root, checked after resolve(),
    so a name carrying a separator is not a project at all. Nothing gets as far
    as being turned into an argument."""
    client, _ = _app(tmp_path, terminal=("term", L.SLOT))

    assert client.post(f"/project/projects/{name}/open/terminal").status_code == 404
    assert ran == []


def test_the_placeholder_is_filled_in_wherever_it_sits(tmp_path):
    """It used to be matched by EQUALITY, so a flag carrying the path with an
    equals sign was passed through untouched: `gnome-terminal
    --working-directory={}` started in a folder called `{}`. Measured on Fedora,
    where it is three of the terminals in the list.

    The rule that mattered is kept below, and it was never the same rule."""
    launcher = L.Launcher("x", ("x", "--dir=" + L.SLOT, L.SLOT))

    argv = L.build(launcher, "/home/me/p", "/home/me/p/CURRENT_STATUS.md")

    assert argv == ["x", "--dir=/home/me/p", "/home/me/p"]


@pytest.mark.parametrize("folder", [
    "/home/me/two words", "/home/me/a;rm -rf ~", '/home/me/a"b', "/home/me/$(id)",
])
def test_a_path_never_becomes_more_than_one_argument(folder):
    """THE rule, and the reason there is no shell anywhere in this module: a
    command is a list, an element is an argument, and nothing between here and
    the process splits it again. Whatever a folder is called, the command comes
    out with exactly as many arguments as it was written with."""
    launcher = L.Launcher("x", ("x", "--dir=" + L.SLOT, L.SLOT))

    argv = L.build(launcher, folder, folder + "/CURRENT_STATUS.md")

    assert len(argv) == len(launcher.argv)
    assert argv[1] == "--dir=" + folder
    assert argv[2] == folder


def test_every_terminal_in_the_list_gets_a_real_path():
    """Walks the whole table, not just the one this machine happens to have.
    A flag that stops working is invisible here otherwise — which is exactly how
    `--working-directory={}` survived: nobody in this project runs GNOME."""
    for program, args in L.LINUX_TERMINALS:
        launcher = L.Launcher(program, (program,) + args)

        argv = L.build(launcher, "/home/me/p", "/home/me/p/CURRENT_STATUS.md")

        assert L.SLOT not in " ".join(argv), f"{program} keeps the placeholder"
        if args:                      # the ones that take a flag say where
            assert any("/home/me/p" in part for part in argv), program


def test_the_document_is_handed_over_when_the_command_asks_for_it(tmp_path):
    """`{file}` is how a configuration says "this editor opens one file", and it
    is the only way: there is no second setting that could fall out of step."""
    launcher = L.from_config(["notepad", L.SLOT_FILE])

    assert launcher.wants == "file"
    assert L.build(launcher, "/p", "/p/CURRENT_STATUS.md") == [
        "notepad", "/p/CURRENT_STATUS.md"]


def test_a_command_with_no_placeholder_gets_the_folder_appended():
    """What somebody who wrote `editor = ["kate"]` meant."""
    assert L.from_config(["kate"]).argv == ("kate", L.SLOT)


def test_an_empty_command_is_no_command():
    assert L.from_config([]) is None
    assert L.from_config(["", "  "]) is None


# ---- when it may open at all ------------------------------------------------

@pytest.mark.parametrize("bind, launch, expected", [
    ("127.0.0.1", True, True),
    ("localhost", True, True),
    ("::1", True, True),
    ("0.0.0.0", True, False),          # reachable from the network
    ("198.51.100.10", True, False),      # RFC 5737: reserved for documentation
    ("127.0.0.1", False, False),       # switched off by hand
])
def test_opening_needs_both_the_flag_and_a_loopback_bind(bind, launch, expected):
    """Tied to `bind` and not only to the flag: a dashboard reachable from the
    network that starts a terminal on the machine it runs on is a remote shell,
    whatever the person who set `bind` had in mind."""
    cfg = C.Config(roots=[], bind=bind, launch=launch)

    assert L.allowed(cfg) is expected


def test_launch_follows_writable_unless_it_is_said_otherwise():
    """Somebody who asked for a dashboard that does not touch their files did
    not ask for one that runs programs. Saying so explicitly still wins."""
    data = {"roots": [{"path": ANY_ABSOLUTE}]}

    assert C.from_data({**data, "writable": False}).launch is False
    assert C.from_data({**data, "writable": True}).launch is True
    assert C.from_data({**data, "writable": False, "launch": True}).launch is True


def test_a_command_written_as_one_string_is_refused_not_split():
    """Splitting on spaces is a small shell, and a small shell is how
    `C:\\Program Files\\…` becomes two arguments. The message says what to write.
    """
    with pytest.raises(C.ConfigInvalid) as e:
        C.from_data({"roots": [{"path": ANY_ABSOLUTE}],
                     "editor": "code --new-window"})

    assert '["code", "--new-window"]' in str(e.value)


def test_a_single_word_command_is_fine_as_a_string():
    """No spaces, no ambiguity, and it is what people write."""
    cfg = C.from_data({"roots": [{"path": ANY_ABSOLUTE}], "editor": "kate"})

    assert cfg.editor == ("kate",)


# ---- the route --------------------------------------------------------------

def test_the_configured_command_wins_over_the_detected_one(tmp_path, ran):
    """The whole point of issue 1: the editor is no longer decided in the code."""
    client, root = _app(tmp_path, editor=("my-editor", "--wait", L.SLOT))

    r = client.post("/project/projects/prog/open/editor")

    assert r.status_code == 200
    assert ran[0][0] == ["my-editor", "--wait", str(root / "prog")]


def test_it_does_not_wait_for_what_it_started(tmp_path, ran):
    """A terminal outlives the request that opened it. One that dies with the
    response, or fills the server's log with its own output, is not a terminal
    anybody wanted."""
    client, _ = _app(tmp_path, terminal=("term", L.SLOT))

    client.post("/project/projects/prog/open/terminal")

    _, kwargs = ran[0]
    # True everywhere: the server's log is not the terminal's output.
    assert kwargs["stdout"] == L.subprocess.DEVNULL
    assert kwargs["stdin"] == L.subprocess.DEVNULL
    # How "outlives the request" is spelled is not the same word on both
    # systems, and asserting the POSIX one everywhere was a KeyError on Windows.
    # `start_new_session` is POSIX-only and Windows ignores it in SILENCE, which
    # is how a console program once inherited the server's console instead of
    # getting one of its own — so what is checked there is the flag that works.
    if os.name == "posix":
        assert kwargs["start_new_session"] is True
    else:
        assert "start_new_session" not in kwargs, (
            "Windows ignores it without a word, so setting it hides the problem")


def test_a_request_without_the_page_token_opens_nothing(tmp_path, ran):
    """The gate that matters most here. Before it, any page in the browser could
    have reached this route — and this one runs programs."""
    root = _root(tmp_path)
    cfg = C.Config(roots=[F.Root(key="projects", folder=str(root), host=str(root),
                                 prefix="~/", label="P", tags=())],
                   terminal=("term", L.SLOT))
    client = create_app(cfg).test_client()

    r = client.post("/project/projects/prog/open/terminal")

    assert r.status_code == 403
    assert ran == []


def test_a_rebound_name_opens_nothing(tmp_path, ran):
    client, _ = _app(tmp_path, terminal=("term", L.SLOT))

    r = client.post("/project/projects/prog/open/terminal",
                    headers={"Host": "evil.example"})

    assert r.status_code == 403
    assert ran == []


def test_nothing_opens_when_opening_is_off(tmp_path, ran):
    """And the buttons are not on the page either — but the route is the
    barrier, as everywhere else here."""
    client, _ = _app(tmp_path, launch=False, terminal=("term", L.SLOT))

    r = client.post("/project/projects/prog/open/terminal")

    assert r.status_code == 404
    assert ran == []
    assert "button class=\"link open-terminal\"" not in client.get("/").get_data(as_text=True)


@pytest.mark.parametrize("url", [
    "/project/projects/prog/open/browser",       # not a thing that can be opened
    "/project/unknown/prog/open/terminal",       # not a declared root
    "/project/projects/absent/open/terminal",    # not a project
])
def test_there_is_nothing_else_to_open(tmp_path, ran, url):
    client, _ = _app(tmp_path, terminal=("term", L.SLOT))

    assert client.post(url).status_code == 404
    assert ran == []


def test_a_command_that_is_not_installed_says_so(tmp_path, monkeypatch):
    """The one failure that CAN be told apart. Whether a window appeared is not
    knowable from the server, and the route does not pretend it is."""
    def refuse(*a, **k):
        raise FileNotFoundError(2, "No such file or directory")
    monkeypatch.setattr(L.subprocess, "Popen", refuse)
    client, _ = _app(tmp_path, terminal=("not-installed", L.SLOT))

    r = client.post("/project/projects/prog/open/terminal")

    assert r.status_code == 500
    assert "not-installed" in r.get_json()["error"]


def test_the_answer_names_the_program(tmp_path, ran):
    """So the page can say what it opened, which the link it replaces could
    never do — that was the whole complaint about the old buttons."""
    client, _ = _app(tmp_path, terminal=("term", L.SLOT))

    body = client.post("/project/projects/prog/open/terminal").get_json()

    assert body == {"opened": "terminal", "with": "term"}


# ---- detection --------------------------------------------------------------

# ---- stock only, and that is the whole point -------------------------------
#
# Frontstep used to hard-code `vscode://`. It worked beautifully for people who
# had VS Code — that is, for everybody who did not have the problem. What is
# detected now is what came WITH the system, and these tests are what stops a
# well-meaning patch from quietly putting a favourite editor back at the top.

@pytest.mark.parametrize("system, wsl, expected", [
    # On Windows the shell verb is reached through the API, so there is no
    # command line at all — see `shell_open`. From WSL the same verb has to go
    # through the interop layer, because `os.startfile` does not exist on Linux.
    ("Windows", False, (L.SLOT_FILE,)),
    ("Linux", True, ("cmd.exe", "/c", "start", "", L.SLOT_FILE)),   # WSL: Windows decides
    ("Darwin", False, ("open", "-t", L.SLOT_FILE)),
    ("Linux", False, ("xdg-open", L.SLOT_FILE)),
])
def test_the_editor_is_whatever_the_system_opens_the_document_with(
        monkeypatch, system, wsl, expected):
    """Not an editor Frontstep picked: a question put to the system, whose
    answer is a choice the user already made in their own settings.

    Plenty of machines have `.md` registered to something other than Notepad,
    and on those, naming Notepad would override a choice already made — the same
    mistake as hard-coding `vscode://`, one size down."""
    monkeypatch.setattr(L.platform, "system", lambda: system)
    monkeypatch.setattr(L, "in_wsl", lambda: wsl)
    monkeypatch.setattr(L, "_which", lambda *n: "/usr/bin/xdg-open")

    assert L.detect_editor().argv == expected


@pytest.mark.parametrize("installed", ["code", "codium", "cursor", "subl", "zed",
                                       "kitty", "alacritty", "wezterm"])
def test_an_editor_somebody_installed_is_never_picked_for_them(monkeypatch, installed):
    """Having VS Code on the machine must not change what the button does.
    Choosing between the editors somebody might have installed is choosing for
    them; the system's own default is a choice they have already made."""
    monkeypatch.setattr(L.platform, "system", lambda: "Linux")
    monkeypatch.setattr(L, "in_wsl", lambda: False)
    monkeypatch.setattr(L, "has_display", lambda: True)
    monkeypatch.setattr(
        L, "_which",
        lambda *n: "/usr/bin/x" if {installed, "xdg-open"} & set(n) else "")

    assert L.detect_editor().argv == ("xdg-open", L.SLOT_FILE)
    assert L.detect_terminal() is None      # nothing stock installed, so nothing


def test_naming_your_own_editor_still_wins(monkeypatch, tmp_path, ran):
    """The other half of the same rule: the default excludes nobody, and one
    line of configuration gets you the editor you actually use."""
    client, root = _app(tmp_path, editor=("code", L.SLOT))

    client.post("/project/projects/prog/open/editor")

    assert ran[0][0] == ["code", str(root / "prog")]


def test_the_stock_editor_is_given_the_document_not_the_folder(tmp_path, ran, monkeypatch):
    """A stock editor opens a FILE. Handing Notepad a folder would open nothing
    and say something unhelpful about it."""
    monkeypatch.setattr(L, "detect_editor",
                        lambda: L.Launcher("Notepad", ("notepad", L.SLOT_FILE),
                                           wants="file"))
    client, root = _app(tmp_path)

    client.post("/project/projects/prog/open/editor")

    assert ran[0][0] == ["notepad", str(root / "prog" / "CURRENT_STATUS.md")]


def test_detection_asks_the_system_instead_of_assuming(monkeypatch):
    """The old Editor button assumed VS Code and had nothing to say when it was
    wrong. With nothing installed, the honest answer is None — and None is what
    takes the button off the page."""
    monkeypatch.setattr(L, "_which", lambda *names: "")
    monkeypatch.setattr(L.platform, "system", lambda: "Linux")
    monkeypatch.setattr(L, "in_wsl", lambda: False)

    assert L.detect_terminal() is None
    assert L.detect_editor() is None


def test_on_wsl_the_terminal_is_the_one_windows_is_set_to_use(monkeypatch):
    """`start` opens a console, and WHICH console is the user's own Windows
    setting — so somebody who uses Windows Terminal gets Windows Terminal
    without Frontstep ever naming it.

    A Linux terminal drawn by WSLg is not the default: it needs WSLg AND a
    terminal emulator installed inside the distribution, neither of which is
    true of a fresh WSL. And where one is installed it may have arrived as
    another package's dependency and never been chosen by anybody, so preferring
    it would mean opening a program the user does not use. `cmd.exe` and
    `wsl.exe` are there by definition if WSL is what you are running.
    """
    monkeypatch.setattr(L, "in_wsl", lambda: True)
    monkeypatch.setattr(L, "has_display", lambda: True)
    monkeypatch.setattr(L, "_which", lambda *n: "/usr/bin/x")   # everything installed

    assert L.detect_terminal().argv == (
        "cmd.exe", "/c", "start", "", "wsl.exe", "--cd", L.SLOT)


def test_no_program_is_named_where_the_system_can_be_asked(monkeypatch):
    """The heart of it. On Windows and macOS the command is a REQUEST — open
    this with whatever the person uses — and on Debian `x-terminal-emulator` is
    that same request in symlink form. None of them names an application, which
    is what makes them impossible to get wrong for somebody else."""
    for system, wsl in (("Windows", False), ("Linux", True), ("Darwin", False)):
        monkeypatch.setattr(L.platform, "system", lambda s=system: s)
        monkeypatch.setattr(L, "in_wsl", lambda w=wsl: w)
        monkeypatch.setattr(L, "_which", lambda *n: "/usr/bin/x")

        for argv in (L.detect_terminal().argv, L.detect_editor().argv):
            named = {"notepad.exe", "wt.exe", "code", "gedit", "kitty",
                     "powershell.exe", "TextEdit"} & set(argv)
            assert not named, f"{system}: names an application — {named}"


def test_a_terminal_with_no_flag_is_started_in_the_folder(tmp_path, ran, monkeypatch):
    """`xterm` and `x-terminal-emulator` take no directory argument: they
    inherit one. Appending the path would make it a command to run."""
    monkeypatch.setattr(L, "detect_terminal", lambda: L.Launcher("xterm", ("xterm",)))
    client, root = _app(tmp_path)

    client.post("/project/projects/prog/open/terminal")

    argv, kwargs = ran[0]
    assert argv == ["xterm"]
    assert kwargs["cwd"] == str(root / "prog")


def test_a_command_that_carries_the_path_is_not_also_started_there(tmp_path, ran, monkeypatch):
    """Measured, and it is not cosmetic: a Windows program started from a WSL
    folder gets a `\\\\wsl.localhost\\…` working directory, and `cmd.exe` refuses
    that outright before it ever reads its arguments. The directory is only for
    the commands that have no other way of being told."""
    monkeypatch.setattr(L, "detect_editor",
                        lambda: L.Launcher("Notepad", ("notepad.exe", L.SLOT_FILE),
                                           wants="file"))
    client, _ = _app(tmp_path)

    client.post("/project/projects/prog/open/editor")

    assert ran[0][1]["cwd"] is None


def test_wsl_is_told_apart_from_plain_linux(monkeypatch, tmp_path):
    """It matters more than it looks: on WSL the programs worth opening are
    Windows ones, reached through interop, and they want a Windows path."""
    monkeypatch.setattr(L.platform, "system", lambda: "Linux")
    version = tmp_path / "version"
    version.write_text("Linux version 6.6.0-microsoft-standard-WSL2")
    monkeypatch.setattr(L, "Path", lambda p: version)

    assert L.in_wsl() is True


# ---- what a real Windows machine taught us ---------------------------------
#
# Measured on a clean Windows 11 install. `cmd.exe /c start "" /D <folder>
# cmd.exe` opens a terminal when TYPED at a prompt, and opens NOTHING when the
# same list goes to subprocess.Popen — while Popen reports success, because
# cmd.exe really did start. The route answered 200 and the user got no window
# and no explanation.

def test_windows_gets_a_console_of_its_own_and_no_shell(monkeypatch):
    """No `cmd /c start`, no empty title, no flag for a shell to re-parse. The
    folder arrives through `cwd`, which is how a process is told where to be
    born."""
    monkeypatch.setattr(L.platform, "system", lambda: "Windows")
    monkeypatch.setattr(L, "in_wsl", lambda: False)

    t = L.detect_terminal()

    assert t.argv == ("cmd.exe",)
    assert t.new_console is True
    assert "start" not in t.argv


def test_a_new_console_is_asked_for_the_windows_way(tmp_path, ran, monkeypatch):
    """`start_new_session` is POSIX-only and Windows ignores it in SILENCE —
    which is how a console program came to inherit the server's console instead
    of getting one of its own, and then not appearing at all."""
    monkeypatch.setattr(L, "detect_terminal",
                        lambda: L.Launcher("term", ("cmd.exe",), new_console=True))
    monkeypatch.setattr(L.subprocess, "CREATE_NEW_CONSOLE", 0x10, raising=False)
    client, root = _app(tmp_path)

    client.post("/project/projects/prog/open/terminal")

    _, kwargs = ran[0]
    assert kwargs["creationflags"] == 0x10
    assert "start_new_session" not in kwargs
    assert kwargs["cwd"] == str(root / "prog")      # the only way it is told


@pytest.mark.skipif(os.name != "posix", reason=(
    "this one fakes POSIX by patching `os.name`, and the pretence only holds "
    "on a system that is already POSIX — elsewhere the rest of `run()` takes "
    "the real system's path and nothing is started at all. The half that says "
    "the flag is NOT set off-POSIX is checked above, on the real system."))
def test_the_posix_flag_is_only_used_on_posix(tmp_path, ran, monkeypatch):
    """The other half: where it means something, it is still there."""
    monkeypatch.setattr(L, "detect_terminal", lambda: L.Launcher("xterm", ("xterm",)))
    monkeypatch.setattr(L.os, "name", "posix")
    client, _ = _app(tmp_path)

    client.post("/project/projects/prog/open/terminal")

    assert ran[0][1]["start_new_session"] is True


def test_windows_opens_a_document_through_the_api_not_a_command_line(tmp_path, monkeypatch):
    """`os.startfile` IS the double-click. Reaching the same shell verb through
    a command line means quoting a path, handing it to a shell and having it
    parsed again — three chances to get it wrong, for no gain."""
    opened = []
    monkeypatch.setattr(L.os, "startfile", lambda p: opened.append(p), raising=False)
    monkeypatch.setattr(L, "detect_editor",
                        lambda: L.Launcher("Windows", (L.SLOT_FILE,),
                                           wants="file", shell_open=True))
    monkeypatch.setattr(L.subprocess, "Popen",
                        lambda *a, **k: pytest.fail("it must not go through a shell"))
    client, root = _app(tmp_path)

    r = client.post("/project/projects/prog/open/editor")

    assert r.status_code == 200
    assert opened == [str(root / "prog" / "CURRENT_STATUS.md")]


def test_a_shell_open_that_fails_is_reported_like_any_other(tmp_path, monkeypatch):
    """It is the one failure that can still be told apart, and the page says it."""
    def refuse(path):
        raise OSError(2, "No application is associated with this file")
    monkeypatch.setattr(L.os, "startfile", refuse, raising=False)
    monkeypatch.setattr(L, "detect_editor",
                        lambda: L.Launcher("Windows", (L.SLOT_FILE,),
                                           wants="file", shell_open=True))
    client, _ = _app(tmp_path)

    r = client.post("/project/projects/prog/open/editor")

    assert r.status_code == 500
    assert "Windows" in r.get_json()["error"]


def test_a_console_of_its_own_keeps_its_own_streams(tmp_path, ran, monkeypatch):
    """The fix for the fix, measured on Windows: with a console of its own the
    window opened and vanished in the same instant, because `cmd.exe` READS
    standard input and DEVNULL is end-of-input.

    The redirection exists so a terminal cannot fill the server's log. Where the
    process has its own console the streams go there anyway, so redirecting them
    buys nothing and costs the window.
    """
    monkeypatch.setattr(L, "detect_terminal",
                        lambda: L.Launcher("term", ("cmd.exe",), new_console=True))
    client, _ = _app(tmp_path)

    client.post("/project/projects/prog/open/terminal")

    _, kwargs = ran[0]
    assert "stdin" not in kwargs, "DEVNULL on stdin closes the terminal at once"
    assert "stdout" not in kwargs and "stderr" not in kwargs


def test_everything_else_still_says_nothing_to_the_log(tmp_path, ran, monkeypatch):
    """The other half: where there is no console of its own, the streams are
    still sent nowhere — a terminal's output is not the server's business."""
    monkeypatch.setattr(L, "detect_terminal", lambda: L.Launcher("xterm", ("xterm",)))
    client, _ = _app(tmp_path)

    client.post("/project/projects/prog/open/terminal")

    _, kwargs = ran[0]
    assert kwargs["stdin"] == L.subprocess.DEVNULL
    assert kwargs["stdout"] == L.subprocess.DEVNULL


def test_a_quote_in_a_path_is_refused_where_cmd_would_reparse_it(tmp_path, ran):
    """⚠️ The one place where "argv is a list, so nothing is parsed" stops being
    true: under WSL the argv reaches `cmd.exe`, and the interop layer rebuilds a
    command line that cmd parses again. A `"` closes the quoting and what follows
    runs as a second command — measured on WSL.

    Legal in a POSIX folder name, forbidden in a Windows one, so refusing it
    takes away nothing that works.
    """
    launcher = L.Launcher("cmd", ("cmd.exe", "/c", "start", "", "wsl.exe", "--cd", L.SLOT))

    with pytest.raises(L.LaunchFailed, match='cannot be passed through cmd.exe'):
        L.run(launcher, '/home/me/proj" & calc.exe & "x', "/home/me/proj/CURRENT_STATUS.md")

    assert ran == [], "nothing may be started"


def test_a_quote_is_fine_where_no_shell_ever_sees_it(tmp_path, ran):
    """The refusal is about `cmd.exe`, not about the character: a POSIX terminal
    takes the name as the one argument it is."""
    launcher = L.Launcher("term", ("term", "-d", L.SLOT))

    L.run(launcher, '/home/me/proj"quoted"', "/home/me/proj/CURRENT_STATUS.md")

    argv, _ = ran[0]
    assert argv == ["term", "-d", '/home/me/proj"quoted"']
