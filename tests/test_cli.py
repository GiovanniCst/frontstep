"""Tests for the command line.

The sore point here is not the parsing, it is WHAT GETS WRITTEN and where. Two
commands touch folders that belong to the user, so most of these tests are about
files that must NOT change.
"""
import datetime as dt
import io
import sys
from pathlib import Path

import pytest

from frontstep import cli, config as C, core as F

from conftest import pretend_home


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake home with three projects and no status document anywhere."""
    code = tmp_path / "code"
    for name in ("alpha", "beta", "gamma"):
        (code / name).mkdir(parents=True)
    (code / "alpha" / "README.md").write_text(
        "# Alpha\n\nA small tool that reconciles warehouse movements with the "
        "documents that generated them.\n", encoding="utf-8")
    (code / "beta" / "main.py").write_text("print('x')\n", encoding="utf-8")
    pretend_home(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("FRONTSTEP_CONFIG", raising=False)
    return tmp_path


def run(*argv) -> int:
    return cli.main(list(argv))


def files_under(folder: Path) -> set[str]:
    """Every file under `folder`, as `/`-separated relative paths.

    `as_posix()` so the expected sets below read the same everywhere: the
    question these tests ask is WHICH files exist, and the separator a system
    happens to write is not part of it.
    """
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


# ---- init ------------------------------------------------------------------

def test_init_writes_the_config_and_one_example(home, capsys):
    code = home / "code"
    before = files_under(code)

    assert run("init", "--config", str(home / "c.toml"), "--root", f"{code}:Code:work") == 0

    assert (home / "c.toml").is_file()
    written = files_under(code) - before
    # Exactly one file, and it is inside a folder init made itself.
    assert written == {f"{cli.EXAMPLE_FOLDER}/CURRENT_STATUS.md"}


def test_init_never_touches_an_existing_project(home):
    """The whole point of the onboarding: a tool that writes into forty folders
    of yours on first run is one you uninstall."""
    code = home / "code"
    before = {p: p.read_bytes() for p in code.rglob("*") if p.is_file()}

    run("init", "--config", str(home / "c.toml"), "--root", str(code))

    for path, content in before.items():
        assert path.read_bytes() == content, f"{path} was modified"


def test_the_example_document_is_readable_by_the_dashboard(home):
    """It is the first card anyone sees: if its own header did not parse, the
    tutorial would be teaching something that does not work."""
    code = home / "code"
    run("init", "--config", str(home / "c.toml"), "--root", f"{code}:Code:work")

    root = F.Root(key="code", folder=str(code), host=str(code), prefix="~/code/",
                  tags=("work",))
    project = F.read_project(code / cli.EXAMPLE_FOLDER, root)

    assert project.status == F.ACTIVE
    assert project.description and not project.description_derived
    assert project.next_step
    assert "example" in project.tags


def test_init_refuses_to_overwrite_without_force(home, capsys):
    target = home / "c.toml"
    assert run("init", "--config", str(target), "--root", str(home / "code")) == 0
    assert run("init", "--config", str(target), "--root", str(home / "code")) == 1
    assert "--force" in capsys.readouterr().out


def test_the_config_written_can_be_read_back(home):
    from frontstep import config as C

    code = home / "code"
    run("init", "--config", str(home / "c.toml"),
        "--root", f"{code}:Work stuff:work,oss", "--port", "9100", "--stale-days", "14")
    cfg = C.load(home / "c.toml")

    assert [r.label for r in cfg.roots] == ["Work stuff"]
    assert cfg.roots[0].tags == ("work", "oss")
    assert (cfg.port, cfg.stale_days, cfg.bind) == (9100, 14, "127.0.0.1")


@pytest.mark.parametrize("raw, path, label, tags", [
    (r"C:\Users\me\code",                r"C:\Users\me\code",   "",      []),
    (r"C:\Users\me\code:Work:work,oss",  r"C:\Users\me\code",   "Work",  ["work", "oss"]),
    (r"\\srv\share\code:Shared",         r"\\srv\share\code",   "Shared", []),
    ("/home/me/code",                    "/home/me/code",       "",      []),
    ("/home/me/code:Lavoro:work",        "/home/me/code",       "Lavoro", ["work"]),
])
def test_a_root_with_a_drive_letter_is_not_cut_at_the_colon(raw, path, label, tags):
    """⚠️ `--root` separates PATH from LABEL with a colon, and a Windows path has
    one of its own: splitting naively gives a root called `C`.

    Every case runs on every system: the parsing is about the shape of the
    string, not about where it is being parsed.
    """
    assert cli._split_root(raw) == (path, label, tags)


def test_read_only_is_written_into_the_config(home):
    from frontstep import config as C

    run("init", "--config", str(home / "c.toml"), "--root", str(home / "code"), "--read-only")
    assert C.load(home / "c.toml").writable is False


# ---- adopt -----------------------------------------------------------------

@pytest.fixture
def configured(home):
    run("init", "--config", str(home / "c.toml"), "--root", f"{home / 'code'}:Code:work")
    return home


def test_adopt_dry_run_writes_nothing(configured, capsys):
    code = configured / "code"
    before = files_under(code)

    assert run("adopt", "--config", str(configured / "c.toml"), "--dry-run") == 0

    assert files_under(code) == before
    assert "nothing written" in capsys.readouterr().out


def test_adopt_writes_one_document_per_folder(configured):
    code = configured / "code"
    assert run("adopt", "--config", str(configured / "c.toml"), "--all") == 0

    for name in ("alpha", "beta", "gamma"):
        assert (code / name / "CURRENT_STATUS.md").is_file()
    # and nothing else appeared
    assert files_under(code) == {
        "alpha/README.md", "alpha/CURRENT_STATUS.md",
        "beta/main.py", "beta/CURRENT_STATUS.md",
        "gamma/CURRENT_STATUS.md",
        f"{cli.EXAMPLE_FOLDER}/CURRENT_STATUS.md",
    }


def test_adopt_takes_the_description_from_the_readme(configured):
    code = configured / "code"
    run("adopt", "--config", str(configured / "c.toml"), "--all")

    alpha = (code / "alpha" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "reconciles warehouse movements" in alpha


def test_adopt_leaves_the_description_empty_when_there_is_nothing_to_take(configured):
    """An empty field is honest: the page says "no description" instead of
    showing one that was made up."""
    code = configured / "code"
    run("adopt", "--config", str(configured / "c.toml"), "--all")

    beta = (code / "beta" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Description:**\n" in beta


def test_adopt_leaves_next_step_empty(configured):
    """It cannot be inferred from files, and inventing it is worse than a blank:
    somebody would act on it."""
    code = configured / "code"
    run("adopt", "--config", str(configured / "c.toml"), "--all")

    for name in ("alpha", "beta", "gamma"):
        text = (code / name / "CURRENT_STATUS.md").read_text(encoding="utf-8")
        assert "**Next step:**\n" in text


def test_adopt_dates_from_the_files_not_from_today(configured):
    """`Updated` is a measure, not a guess: the most recent change inside the
    folder. Writing today's date would say work happened when it did not."""
    code = configured / "code"
    old = dt.datetime(2026, 3, 1, 12, 0).timestamp()
    import os
    os.utime(code / "alpha" / "README.md", (old, old))

    run("adopt", "--config", str(configured / "c.toml"), "--all")

    alpha = (code / "alpha" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Updated:** 2026-03-01" in alpha


def test_adopt_ignores_git_and_venv_when_dating(configured):
    """A `git fetch` or a `pip install` is not work on the project."""
    code = configured / "code"
    import os
    old = dt.datetime(2026, 3, 1, 12, 0).timestamp()
    os.utime(code / "beta" / "main.py", (old, old))
    (code / "beta" / ".git").mkdir()
    (code / "beta" / ".git" / "FETCH_HEAD").write_text("now", encoding="utf-8")

    run("adopt", "--config", str(configured / "c.toml"), "--all")

    beta = (code / "beta" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Updated:** 2026-03-01" in beta


def test_adopt_can_set_the_status(configured):
    code = configured / "code"
    run("adopt", "--config", str(configured / "c.toml"), "--all", "--status", "paused")

    text = (code / "alpha" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Status:** paused" in text


def test_adopt_skips_folders_that_already_have_a_document(configured, capsys):
    code = configured / "code"
    run("adopt", "--config", str(configured / "c.toml"), "--all")
    before = (code / "alpha" / "CURRENT_STATUS.md").read_text(encoding="utf-8")

    assert run("adopt", "--config", str(configured / "c.toml"), "--all") == 0

    assert (code / "alpha" / "CURRENT_STATUS.md").read_text(encoding="utf-8") == before
    assert "already" in capsys.readouterr().out


def test_adopt_without_a_config_says_how_to_make_one(home, capsys):
    assert run("adopt", "--config", str(home / "nope.toml")) == 1
    assert "No configuration found" in capsys.readouterr().out


# ---- skill -----------------------------------------------------------------

def test_skill_print_writes_nothing(home, capsys):
    assert run("skill", "--print") == 0
    out = capsys.readouterr().out
    assert "frontstep-status" in out and "**Status:**" in out


def test_skill_install_claude_writes_the_skill(home):
    target = home / "skills" / "SKILL.md"
    assert run("skill", "--install", "claude", "--target", str(target)) == 0
    assert "name: frontstep-status" in target.read_text(encoding="utf-8")


def test_skill_install_agents_appends_to_an_existing_file(home):
    target = home / "AGENTS.md"
    target.write_text("# My project\n\nSome existing instructions.\n", encoding="utf-8")

    run("skill", "--install", "agents", "--target", str(target))
    text = target.read_text(encoding="utf-8")

    assert "Some existing instructions." in text, "the existing file was overwritten"
    assert "frontstep:begin" in text


def test_skill_install_agents_twice_replaces_its_own_section(home):
    """Installing again must not stack two copies of the same instructions."""
    target = home / "AGENTS.md"
    target.write_text("# My project\n\nSome existing instructions.\n", encoding="utf-8")

    run("skill", "--install", "agents", "--target", str(target))
    run("skill", "--install", "agents", "--target", str(target))
    text = target.read_text(encoding="utf-8")

    assert text.count("frontstep:begin") == 1
    assert text.count("Some existing instructions.") == 1


# ---- serve -----------------------------------------------------------------

def test_serve_without_a_config_starts_and_asks_in_the_browser(home, capsys, monkeypatch):
    """It used to stop and name the command that fixes it. It now starts, and
    the page asks — which for an application whose entire interface IS a page is
    the only sensible first move.

    The reasoning behind the old behaviour is not discarded: a dashboard that
    comes up pointing at some plausible folder looks broken. A page that asks
    where to look is not that page.
    """
    started = {}
    monkeypatch.setattr("flask.Flask.run",
                        lambda self, **kw: started.update(kw, app=self))

    assert run("serve", "--config", str(home / "nope.toml")) == 0

    out = capsys.readouterr().out
    assert started, "it has to actually serve"
    # The address is printed WITH the key: without it that line is useless, and
    # a person who has to assemble a URL by hand has not been onboarded.
    key = started["app"].config["FRONTSTEP_TOKEN"]
    assert f"/?key={key}" in out
    assert "not set up yet" in out


def test_serve_refuses_a_configuration_that_exists_but_is_broken(home, capsys):
    """Setup would be the wrong answer here: it would offer to write over
    something somebody has already written. Only a MISSING file means first
    run."""
    broken = home / "broken.toml"
    broken.write_text("roots = 12\n", encoding="utf-8")

    assert run("serve", "--config", str(broken)) == 1
    assert "Configuration problem" in capsys.readouterr().out


# ---- doctor ----------------------------------------------------------------
#
# Every check it makes is something that failed on a real machine. The tests
# below are about the ONE property that makes it worth having: it must be
# readable and honest when everything is missing, because that is exactly when
# somebody runs it.

def test_doctor_works_with_nothing_configured(home, capsys):
    """The first run of all: no configuration, no roots, nothing adopted."""
    code = run("doctor")
    out = capsys.readouterr().out

    assert code == 0, "nothing here stops it working, so it must not fail"
    assert "Python" in out
    assert "configuration" in out
    assert str(C.default_path()) in out, "it says where the file would go"


def test_doctor_says_how_to_run_it_when_the_command_is_not_on_path(home, capsys, monkeypatch):
    """It happened on Windows: installed, warned about by pip, and unusable. The
    way out has to be in the output, not in a README the person is not reading at
    that moment.

    ⚠️ It used to offer `python -m frontstep`, which does NOT work after the
    install this project recommends: `uv tool install` puts the package in an
    isolated environment, so the system Python has never heard of it — verified,
    `No module named frontstep`. The advice now names the scripts directory and
    `uv tool update-shell`, which are the two things that do work.
    """
    monkeypatch.setattr("shutil.which", lambda name: None)

    run("doctor")

    out = capsys.readouterr().out
    assert "uv tool update-shell" in out
    assert "python -m frontstep" not in out, "that route does not exist after `uv tool install`"


def test_doctor_names_what_the_two_buttons_would_open(home, capsys):
    """They vanish rather than fail when there is nothing to open with, and a
    button missing without explanation is its own kind of bug."""
    run("doctor")
    out = capsys.readouterr().out

    assert "opening a terminal" in out
    assert "opening an editor" in out


def test_doctor_fails_only_on_what_stops_it_working(home, capsys, monkeypatch):
    """A `·` is worth knowing and not worth failing over — most first runs have
    several. Exit 1 has to mean something."""
    monkeypatch.setattr(cli.sys, "version_info", (3, 9, 0))

    assert run("doctor") == 1
    assert "3.11" in capsys.readouterr().out


class Console(io.TextIOBase):
    """A console that refuses what its codepage cannot hold, like a real one.

    `io.StringIO` accepts every character regardless of the `encoding` it
    reports, so it cannot reproduce this failure at all — the write has to be
    the thing that raises.
    """

    def __init__(self, encoding):
        self._encoding = encoding
        self.out = []

    @property
    def encoding(self):
        return self._encoding

    def write(self, text):
        text.encode(self._encoding)      # what a real console does
        self.out.append(text)
        return len(text)

    def value(self):
        return "".join(self.out)


def test_doctor_survives_a_console_that_cannot_print_a_tick(home, monkeypatch):
    """⚠️ Found on a Windows runner, and it had never run this suite before: the
    console there encodes cp1252, `✓` is not in cp1252, and `doctor` died with
    UnicodeEncodeError on its FIRST line — the one command whose entire job is
    to report on a machine that is not working.

    Asked of the stream, not of the platform, so this is reproducible anywhere.
    """
    console = Console("cp1252")
    monkeypatch.setattr(cli.sys, "stdout", console)

    code = run("doctor")

    assert code == 0
    assert "Python" in console.value(), "it still says what it found"


def test_the_three_marks_are_all_real_or_all_plain(home):
    """⚠️ The trap inside the fix above: `·` IS in cp1252 and `✓` is not, so
    deciding per symbol prints a two-character `ok` on one row and a
    one-character `·` on the next, and bends the column between them.

    Whatever the console, the three marks are the same width as each other.
    """
    for encoding in ("cp1252", "utf-8", "ascii"):
        shown = cli.marks(Console(encoding))
        widths = {len(mark) for mark in shown.values()}
        assert len(widths) == 1, f"{encoding}: marks of different widths {shown}"


def test_a_path_no_codepage_covers_does_not_silence_the_report(home, monkeypatch):
    """The last resort, and it is the same failure one step further along: a
    folder named in Greek must not be what stops `doctor` reporting — least of
    all on the console that cannot spell it."""
    console = Console("cp1252")
    monkeypatch.setattr(cli.sys, "stdout", console)

    cli.say("  ✓ /projects/Ελληνικά/έργο")

    assert console.value().strip().startswith("ok"), "the mark came through"


def test_python_m_frontstep_is_a_real_way_in():
    """The three lines that make the application startable where the scripts
    folder is not on PATH. A missing `__main__.py` is not a traceback, it is an
    app that cannot be started."""
    import subprocess as sp

    done = sp.run([sys.executable, "-m", "frontstep", "--version"],
                  capture_output=True, text=True, timeout=30)

    assert done.returncode == 0
    assert "frontstep" in done.stdout.lower()

    # and `doctor` through the same door, because that is the one somebody runs
    # when nothing else works
    checked = sp.run([sys.executable, "-m", "frontstep", "doctor"],
                     capture_output=True, text=True, timeout=60)
    assert "Python" in checked.stdout


def test_doctor_does_not_call_a_headless_machine_broken(home, capsys, monkeypatch):
    """A server or a CI runner has no terminal and no editor installed, and is a
    perfectly good place to run a dashboard: the page works and those two
    buttons are simply not on the cards.

    This is the difference the exit code has to carry. It was wrong once — the
    checks marked "nothing to open with" as fatal, and every CI run went red on
    a machine where nothing was actually wrong.
    """
    from frontstep import launch as L
    monkeypatch.setattr(L, "detect_terminal", lambda: None)
    monkeypatch.setattr(L, "detect_editor", lambda: None)

    code = run("doctor")
    out = capsys.readouterr().out

    assert code == 0, "no desktop is not a fault"
    assert "will not be there" in out, "but it has to say the buttons will be missing"
