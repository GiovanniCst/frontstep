"""The first run: the page that asks where the projects are, and writes the file.

This is the FOURTH place Frontstep writes and by some distance the most
dangerous one. The other three rewrite a named line of a header; this one writes
the file that decides `bind`, `writable`, and which commands may be run. A hole
here is not a wrong date on a card.

So the weight of this file is on what the route REFUSES: without the key from
the terminal, without the page token, and once a configuration already exists.
"""
from pathlib import Path

import pytest

from frontstep import config as C, core as F
from frontstep.web import create_app

from conftest import pretend_home


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home folder of our own, so nothing here can see the real one."""
    pretend_home(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    (tmp_path / "projects" / "one").mkdir(parents=True)
    (tmp_path / "projects" / "one" / "CURRENT_STATUS.md").write_text(
        "# One\n\n**Status:** active\n**Updated:** 2026-01-05\n"
        "**Next step:** Keep going\n", encoding="utf-8")
    (tmp_path / "projects" / "two").mkdir()
    return tmp_path


@pytest.fixture
def fresh(home):
    """An app with NO configuration: what a first run actually looks like."""
    app = create_app(None)
    client = app.test_client()
    return app, client


def _payload(home, **over):
    body = {"roots": [{"path": str(home / "projects"), "label": "Projects",
                       "tags": ["work"]}],
            "language": "en", "stale_days": 7, "writable": True}
    body.update(over)
    return body


# ---- what it refuses -------------------------------------------------------

def test_the_page_needs_the_key_from_the_terminal(fresh):
    """Whoever can see the terminal started the program. On a machine with more
    than one account, being able to reach a port is not the same thing — and
    without this, any local account could point Frontstep at somebody's home
    folder and switch on the commands that run programs."""
    _, client = fresh

    r = client.get("/")

    assert r.status_code == 403
    body = r.get_data(as_text=True)
    assert "terminal" in body
    assert 'name="frontstep-token"' not in body, "and it must not leak the key"


def test_the_right_key_opens_the_page(fresh):
    app, client = fresh

    r = client.get("/", query_string={"key": app.config["FRONTSTEP_TOKEN"]})

    assert r.status_code == 200
    assert 'id="setup-form"' in r.get_data(as_text=True)


def test_a_wrong_key_is_refused(fresh):
    _, client = fresh

    r = client.get("/", query_string={"key": "not-the-key"})

    assert r.status_code == 403


def test_writing_needs_the_page_token_like_every_other_write(fresh, home):
    """Same gate as the other three writes, and here it matters most."""
    _, client = fresh

    r = client.post("/setup", json=_payload(home))

    assert r.status_code == 403
    assert not (home / ".config" / "frontstep" / "config.toml").exists()


def test_a_rebound_name_cannot_set_frontstep_up(fresh, home):
    app, client = fresh

    r = client.post("/setup", json=_payload(home),
                    headers={"X-Frontstep-Token": app.config["FRONTSTEP_TOKEN"],
                             "Host": "evil.example"})

    assert r.status_code == 403
    assert not (home / ".config" / "frontstep" / "config.toml").exists()


def test_setup_cannot_run_twice(tmp_path, home):
    """The route may only ever create the FIRST configuration. One that could
    rewrite it at any time would be a route that can switch `writable` back on,
    or point the dashboard somewhere else, for the life of the process."""
    cfg = C.Config(roots=[F.Root(key="p", folder=str(home / "projects"),
                                 host=str(home / "projects"), prefix="~/",
                                 label="P", tags=())])
    app = create_app(cfg)
    client = app.test_client()

    r = client.post("/setup", json=_payload(home),
                    headers={"X-Frontstep-Token": app.config["FRONTSTEP_TOKEN"]})

    assert r.status_code == 403
    assert "already configured" in r.get_json()["error"]


# ---- what it writes --------------------------------------------------------

def _setup(app, client, home, **over):
    return client.post("/setup", json=_payload(home, **over),
                       headers={"X-Frontstep-Token": app.config["FRONTSTEP_TOKEN"]})


def test_it_writes_the_file_and_serves_it_without_a_restart(fresh, home):
    """The whole point of doing this in the browser. Telling somebody who has
    just filled in a form to go back to a terminal and start the program again
    is not an onboarding, it is a detour."""
    app, client = fresh

    r = _setup(app, client, home)

    assert r.status_code == 201
    written = Path(r.get_json()["written"])
    assert written.is_file()
    # and the SAME process is now serving it
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "one" in dashboard.get_data(as_text=True)


def test_what_it_writes_can_be_read_back(fresh, home):
    """The file is the product here, not the response: it is what the next run
    loads, and what the person edits afterwards."""
    app, client = fresh

    _setup(app, client, home, language="it", stale_days=14, writable=False)

    cfg = C.load(home / ".config" / "frontstep" / "config.toml")
    assert cfg.language == "it"
    assert cfg.stale_days == 14
    assert cfg.writable is False
    assert [r.label for r in cfg.roots] == ["Projects"]
    assert cfg.roots[0].tags == ("work",)


def test_it_never_listens_beyond_localhost_on_a_first_run(fresh, home):
    """Not asked on the form, and not an oversight: a first run is not the
    moment to be asked to reason about network exposure."""
    app, client = fresh

    _setup(app, client, home)

    assert C.load(home / ".config" / "frontstep" / "config.toml").bind == "127.0.0.1"


def test_read_only_at_setup_also_means_it_opens_nothing(fresh, home):
    """`launch` follows `writable` when it is not said otherwise, so answering
    "no, do not write in my files" does not quietly leave a dashboard that runs
    programs."""
    app, client = fresh

    _setup(app, client, home, writable=False)

    assert C.load(home / ".config" / "frontstep" / "config.toml").launch is False


# ---- the folders -----------------------------------------------------------

def test_a_folder_that_is_not_there_is_refused_not_created(fresh, home):
    """Onboarding writes nothing inside anybody's projects, and quietly making a
    directory because a path was mistyped is exactly the surprise that rule
    exists to prevent."""
    app, client = fresh
    missing = home / "typo"

    r = _setup(app, client, home,
               roots=[{"path": str(missing), "label": "", "tags": []}])

    assert r.status_code == 400
    assert "no folder there" in r.get_json()["error"]
    assert not missing.exists()


def test_no_folder_at_all_is_refused(fresh, home):
    app, client = fresh

    r = _setup(app, client, home, roots=[])

    assert r.status_code == 400
    assert "At least one folder" in r.get_json()["error"]


def test_a_relative_path_is_refused(fresh, home):
    app, client = fresh

    r = _setup(app, client, home,
               roots=[{"path": "projects", "label": "", "tags": []}])

    assert r.status_code == 400
    assert "absolute" in r.get_json()["error"]


def test_a_tilde_is_expanded(fresh, home):
    """`~/projects` is how people write it, and refusing it over a character
    would be pedantry."""
    app, client = fresh

    r = _setup(app, client, home,
               roots=[{"path": "~/projects", "label": "", "tags": []}])

    assert r.status_code == 201
    cfg = C.load(home / ".config" / "frontstep" / "config.toml")
    assert cfg.roots[0].folder == str(home / "projects")


def test_a_folder_with_no_label_is_named_after_itself(fresh, home):
    """The form asks for a path, not for a name: a folder already has one."""
    app, client = fresh

    _setup(app, client, home,
           roots=[{"path": str(home / "projects"), "label": "", "tags": []}])

    assert C.load(home / ".config" / "frontstep" / "config.toml").roots[0].label == "projects"


def test_the_home_folder_is_never_labelled_with_the_user_name(fresh, home):
    """A home folder's name IS the user name, and the label ends up on screen,
    in element ids and in every screenshot. Same rule as everywhere else."""
    app, client = fresh

    _setup(app, client, home, roots=[{"path": str(home), "label": "", "tags": []}])

    assert C.load(home / ".config" / "frontstep" / "config.toml").roots[0].label == "Home"


# ---- the suggestions -------------------------------------------------------

def test_the_page_offers_folders_that_exist_with_a_count(home):
    """So that a first run is a click rather than a path typed from memory. The
    count is what answers "is this the folder you meant?" with a fact."""
    app = create_app(None)
    client = app.test_client()

    page = client.get("/", query_string={"key": app.config["FRONTSTEP_TOKEN"]}
                      ).get_data(as_text=True)

    assert str(home / "projects") in page
    assert "1 project" in page          # `two` has no status document


def test_the_suggestions_count_only_what_would_be_shown(home):
    """Dot-folders are skipped by `scan`, so counting them would make the number
    a lie — and the number is the only reason the list is useful."""
    (home / "projects" / ".hidden").mkdir()
    (home / "projects" / ".hidden" / "CURRENT_STATUS.md").write_text(
        "# H\n\n**Status:** active\n", encoding="utf-8")

    found = {r["path"]: r for r in F.suggest_roots(home)}

    assert found[str(home / "projects")]["projects"] == 1


def test_the_folder_with_the_most_projects_comes_first(home):
    """Sorted by a measured number, not by a guess about anybody's habits."""
    (home / "code").mkdir()

    assert F.suggest_roots(home)[0]["path"] == str(home / "projects")


def test_nothing_is_suggested_that_does_not_exist(home):
    """Every entry is a folder that is really there — the list is measured, and
    the names in `LIKELY_ROOTS` are only where to look."""
    for entry in F.suggest_roots(home):
        assert Path(entry["path"]).is_dir()


def test_the_port_written_is_the_one_it_is_actually_answering_on(fresh, home):
    """Not on the form and not defaulted: read off the address the request
    arrived at. Somebody who started Frontstep elsewhere because 9015 was taken
    would otherwise get a file saying 9015 and find it moved tomorrow."""
    app, client = fresh

    client.post("/setup", json=_payload(home),
                headers={"X-Frontstep-Token": app.config["FRONTSTEP_TOKEN"],
                         "Host": "127.0.0.1:9019"})

    assert C.load(home / ".config" / "frontstep" / "config.toml").port == 9019


@pytest.mark.parametrize("host, expected", [
    ("127.0.0.1:9019", 9019),
    ("localhost:9015", 9015),
    ("[::1]:9019", 9019),
    ("localhost", 9015),          # no port: Frontstep's own default, not 80
    ("[::1]", 9015),
    ("localhost:0", 9015),        # not a port anybody can listen on
])
def test_the_port_is_read_out_of_the_host_header(host, expected):
    from frontstep.web import _port_of

    assert _port_of(host) == expected


# ---- what a clean machine taught us ----------------------------------------
#
# Every test below is a thing that happens on an empty machine, and none of them
# could fail before — which is the point: they are what a first run looks like
# to somebody who has nothing yet.

def test_a_first_run_never_lands_on_an_empty_dashboard(fresh, home):
    """`init` had always created an example project whose document IS the
    tutorial. The setup page had not — so the way in we had just made the main
    one produced a dashboard with nothing on it, which is the exact thing this
    project decided against."""
    app, client = fresh

    _setup(app, client, home)

    example = home / "projects" / F.EXAMPLE_FOLDER
    assert (example / "CURRENT_STATUS.md").is_file()
    assert "frontstep-example" in client.get("/").get_data(as_text=True)


def test_the_example_never_overwrites_something_already_there(home):
    """Ours is the only folder we make, and if something already has that name
    it is left exactly as it is."""
    mine = home / "projects" / F.EXAMPLE_FOLDER
    mine.mkdir()
    (mine / "CURRENT_STATUS.md").write_text("# Mine\n\n**Status:** active\n", encoding="utf-8")

    assert F.create_example(str(home / "projects")) is None
    assert "# Mine" in (mine / "CURRENT_STATUS.md").read_text()


def test_the_first_suggestion_is_ticked_even_with_nothing_in_it(home):
    """On a first run every count is zero — nobody has written a status document
    yet — so ticking "the first one that has projects" ticked nothing, and
    pressing Start produced an error instead of a dashboard."""
    app = create_app(None)

    page = app.test_client().get(
        "/", query_string={"key": app.config["FRONTSTEP_TOKEN"]}).get_data(as_text=True)

    assert page.count("checked") == 2      # the first root, and `writable`


def test_the_home_folder_is_never_the_first_thing_offered(home):
    """It sorts first by path length when every count is zero, and "scan your
    entire home directory" is not what somebody means by "where are your
    projects"."""
    (home / "code").mkdir()

    assert F.suggest_roots(home)[0]["path"] != str(home)
    assert str(home) in [r["path"] for r in F.suggest_roots(home)]


def test_an_empty_dashboard_does_not_blame_the_filters(tmp_path):
    """It said "No project matches these filters" with every filter at rest,
    and sent the reader looking for a filter to undo."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    cfg = C.Config(roots=[F.Root(key="r", folder=str(empty), host=str(empty),
                                 prefix="~/", label="R", tags=())])
    app = create_app(cfg)

    page = app.test_client().get("/").get_data(as_text=True)

    assert "Nothing to show yet" in page
    assert "CURRENT_STATUS.md" in page          # and it says what would fix it
    assert "New project" in page


def test_a_dashboard_with_projects_keeps_the_filter_message(home):
    """The other message is still needed: filters really can exclude everything."""
    root = home / "projects"
    app = create_app(C.Config(roots=[F.Root(key="r", folder=str(root), host=str(root),
                                            prefix="~/", label="R", tags=())]))

    page = app.test_client().get("/").get_data(as_text=True)

    assert "Nothing to show yet" not in page
    assert 'id="none-match"' in page


# ---- where a configuration goes --------------------------------------------

@pytest.mark.parametrize("osname, platform, expected", [
    ("nt", "win32", ("AppData", "Roaming")),
    ("posix", "darwin", ("Library", "Application Support")),
    ("posix", "linux", (".config",)),
])
def test_the_configuration_goes_where_the_system_keeps_configuration(
        monkeypatch, home, osname, platform, expected):
    """Measured on Windows: Frontstep created `C:\\Users\\…\\.config\\frontstep`,
    a dot-folder in the home directory. It works, and it is a Unix convention in
    a place no other Windows program writes to."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(C.os, "name", osname)
    monkeypatch.setattr(C.sys, "platform", platform)
    monkeypatch.delenv("APPDATA", raising=False)

    where = C.config_home()

    assert where.parts[-len(expected):] == expected


def test_xdg_still_wins_where_somebody_has_set_it(monkeypatch, tmp_path):
    """Somebody who has set it has said where they want this."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "elsewhere"))

    assert C.config_home() == tmp_path / "elsewhere"
