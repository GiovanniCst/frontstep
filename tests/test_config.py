"""Configuration tests: a human writes this file, so it can say anything. The
sore point is that a wrong file gives a message that can be understood, instead
of a traceback or — worse — a dashboard that starts up pointing at the wrong
folder.
"""
from pathlib import Path

import pytest

from conftest import ANY_ABSOLUTE

from frontstep import config as C


def write(folder: Path, text: str, name: str = "frontstep.toml") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


MINIMA = """
[[roots]]
path = "~/projects"
"""


# ---- the bare minimum ----------------------------------------------

def test_one_root_is_enough():
    cfg = C.from_data({"roots": [{"path": "~/lavoro"}]})

    assert len(cfg.roots) == 1
    assert cfg.roots[0].folder == str(Path.home() / "lavoro")
    # The defaults are not in the file: whoever leaves them out still gets them.
    assert (cfg.language, cfg.stale_days, cfg.port) == ("en", 7, 9015)
    assert cfg.bind == "127.0.0.1", "di default si ascolta in locale, non su 0.0.0.0"
    assert cfg.writable is True
    assert cfg.status_filename == "CURRENT_STATUS.md"


def test_no_roots_means_no_start():
    """A configuration with no roots is not an empty configuration: it is a
    dashboard that can show nothing, and that has to be said at once."""
    with pytest.raises(C.ConfigInvalid, match="At least one root"):
        C.from_data({"language": "it"})
    with pytest.raises(C.ConfigInvalid, match="At least one root"):
        C.from_data({"roots": []})


def test_a_root_without_a_path_is_a_readable_error():
    with pytest.raises(C.ConfigInvalid, match=r"entry 2.*`path` is missing"):
        C.from_data({"roots": [{"path": "~/a"}, {"label": "No path"}]})


def test_a_relative_path_is_refused():
    """A relative path depends on where the command was run: the same configuration
    would show different projects depending on the current folder."""
    with pytest.raises(C.ConfigInvalid, match="absolute path"):
        C.from_data({"roots": [{"path": "progetti"}]})


# ---- quante roots si vuole -------------------------------------------------

def test_three_roots_with_their_own_labels_and_keys(posix_paths):
    cfg = C.from_data({"roots": [
        {"path": "~/work", "label": "Lavoro", "tags": ["work"]},
        {"path": "~/side", "label": "Progetti miei", "tags": ["personal", "OSS"]},
        {"path": "/srv/shared", "label": "Condivisi"},
    ]})

    assert [r.key for r in cfg.roots] == ["lavoro", "progetti-miei", "condivisi"]
    assert [r.label for r in cfg.roots] == ["Lavoro", "Progetti miei", "Condivisi"]
    assert cfg.roots[1].tags == ("personal", "oss")
    assert cfg.roots[2].tags == ()
    # The known tags are how the page knows which filters exist before it has
    # read a single document.
    assert cfg.known_tags == ("work", "personal", "oss")


def test_two_roots_cannot_share_a_key():
    """The key is in the URL: two the same would mean two different folders
    with one address, and una scrittura finirebbe nel progetto sbagliato."""
    with pytest.raises(C.ConfigInvalid, match="already belongs to another root"):
        C.from_data({"roots": [
            {"path": "~/a/lavoro"},
            {"path": "~/b/lavoro"},
        ]})


def test_an_explicit_key_breaks_the_collision():
    cfg = C.from_data({"roots": [
        {"path": "~/a/lavoro"},
        {"path": "~/b/lavoro", "key": "lavoro-b"},
    ]})
    assert [r.key for r in cfg.roots] == ["lavoro", "lavoro-b"]


def test_a_key_cannot_be_just_anything():
    with pytest.raises(C.ConfigInvalid, match="not usable"):
        C.from_data({"roots": [{"path": "~/a", "key": "con/barra"}]})


def test_the_prefix_is_how_the_path_reads_on_a_card(posix_paths):
    cfg = C.from_data({"roots": [
        {"path": "~/projects"},
        {"path": "~"},
        {"path": "/srv/repos"},
    ]})
    assert [r.prefix for r in cfg.roots] == ["~/projects/", "~/", "/srv/repos/"]


def test_the_home_folder_gets_a_key_of_its_own():
    """`Path.home().name` is the user name: as a key it would say who you are, and
    it would change from one machine to another."""
    cfg = C.from_data({"roots": [{"path": "~"}]})
    assert cfg.roots[0].key == "home"


# ---- i tag ------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Prod", "prod"),
    ("PROD", "prod"),
    ("  prod  ", "prod"),
    ("in produzione", "in-produzione"),
    ("client_acme", "client-acme"),
    ("`prod`", "prod"),
    ("---", ""),
])
def test_tags_are_normalised(raw, expected):
    """The same tag spelled two ways must not become two filters."""
    assert C.normalize_tag(raw) == expected


def test_duplicate_tags_go_and_the_order_stays():
    cfg = C.from_data({"roots": [{"path": "~/a", "tags": ["Work", "prod", "work"]}]})
    assert cfg.roots[0].tags == ("work", "prod")


def test_a_single_tag_can_be_written_as_a_string():
    """Whoever writes the file by hand writes `tags = "work"`, and they are right."""
    cfg = C.from_data({"roots": [{"path": "~/a", "tags": "work"}]})
    assert cfg.roots[0].tags == ("work",)


def test_tags_of_the_wrong_type_say_so():
    with pytest.raises(C.ConfigInvalid, match="`tags` wants a list"):
        C.from_data({"roots": [{"path": "~/a", "tags": 3}]})


# ---- i valori scalari -------------------------------------------------------

def test_out_of_range_values_are_refused():
    with pytest.raises(C.ConfigInvalid, match="stale_days"):
        C.from_data({"roots": [{"path": "~/a"}], "stale_days": 0})
    with pytest.raises(C.ConfigInvalid, match="port"):
        C.from_data({"roots": [{"path": "~/a"}], "port": 99999})
    with pytest.raises(C.ConfigInvalid, match="expected true or false"):
        C.from_data({"roots": [{"path": "~/a"}], "writable": "si"})


def test_the_status_file_is_a_name_not_a_path():
    """A path in there would mean looking for the document outside the project's
    folder, which is a different thing from what is being asked."""
    with pytest.raises(C.ConfigInvalid, match="a file name, not a path"):
        C.from_data({"roots": [{"path": "~/a"}], "status_file": "docs/STATUS.md"})


def test_the_document_name_can_be_changed():
    cfg = C.from_data({"roots": [{"path": "~/a"}], "status_file": "STATUS.md"})
    assert cfg.status_filename == "STATUS.md"


# ---- where it is read from --------------------------------------------------

def test_the_file_is_read_and_where_from_is_remembered(tmp_path):
    p = write(tmp_path, MINIMA)
    cfg = C.load(p)

    assert cfg.path == p
    assert len(cfg.roots) == 1


def test_with_no_file_it_says_where_it_looked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv(C.PATH_ENV_VAR, raising=False)

    with pytest.raises(C.ConfigMissing) as e:
        C.load()
    # The message lists the places it looked: without them, whoever reads it
    # still does not know where to put the file.
    assert "frontstep.toml" in str(e.value)
    assert str(tmp_path / "config") in str(e.value)


def test_the_lookup_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv(C.PATH_ENV_VAR, str(tmp_path / "esplicito.toml"))

    trovati = [str(p) for p in C.candidate_paths()]
    assert trovati == [
        str(tmp_path / "esplicito.toml"),
        str(tmp_path / "frontstep.toml"),
        str(tmp_path / "xdg" / "frontstep" / "config.toml"),
    ]


def test_the_file_next_to_the_project_beats_the_user_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv(C.PATH_ENV_VAR, raising=False)
    write(tmp_path, '[[roots]]\npath = "~/qui"\n')
    write(tmp_path / "xdg" / "frontstep", '[[roots]]\npath = "~/altrove"\n', "config.toml")

    assert C.load().roots[0].folder.endswith("qui")


def test_broken_toml_says_so_without_a_traceback(tmp_path):
    p = write(tmp_path, "[[roots]\npath = ~/a\n")
    with pytest.raises(C.ConfigInvalid, match="invalid TOML"):
        C.load(p)


# ---- environment variables win over the file -------------------------------

def test_the_environment_overrides_the_file(tmp_path, monkeypatch):
    """This serves a container, which may not have the file mounted."""
    p = write(tmp_path, MINIMA + '\nport = 9015\nstale_days = 7\n')
    monkeypatch.setenv("FRONTSTEP_PORT", "8123")
    monkeypatch.setenv("FRONTSTEP_STALE_DAYS", "30")
    monkeypatch.setenv("FRONTSTEP_BIND", "0.0.0.0")
    monkeypatch.setenv("FRONTSTEP_WRITABLE", "false")

    cfg = C.load(p)

    assert (cfg.port, cfg.stale_days, cfg.bind) == (8123, 30, "0.0.0.0")
    assert cfg.writable is False
    # and the rest of the file stays what the file says
    assert len(cfg.roots) == 1


def test_the_environment_cannot_declare_roots(tmp_path, monkeypatch):
    """Roots are a structure: passing them through an environment variable is how
    you get them wrong, and it is not supported. They stay in the file."""
    p = write(tmp_path, MINIMA)
    monkeypatch.setenv("FRONTSTEP_ROOTS", "/tmp/altro")

    assert [r.folder for r in C.load(p).roots] == [str(Path.home() / "projects")]


# ---- the host-side path (containers) --------------------------------------

def test_host_path_for_running_in_a_container(tmp_path):
    """In a container the folder is mounted elsewhere: what gets copied from a card
    has to be the path on the machine of whoever is looking, not the
    container's."""
    inside = ANY_ABSOLUTE          # where the folder is mounted in the container
    cfg = C.from_data({"roots": [{"path": inside, "host_path": "~/lavoro"}]})
    r = cfg.roots[0]

    assert r.folder == inside
    assert r.host == str(Path.home() / "lavoro")
    # ⚠️ And the prefix, which is the address WRITTEN ON THE CARD: built from the
    # container's path it read `/projects/…`, the one address the person looking
    # at the card cannot use.
    #
    # Asserted by what it NAMES, not by how it is spelled: the home shortening is
    # `~/` on POSIX and `%USERPROFILE%\` on Windows, and both are correct — the
    # first version of this test only knew the first, and said so on a Windows
    # runner.
    assert "lavoro" in r.prefix
    assert r.prefix != C._prefix_from(Path(inside)), "still built from the container's path"


def test_without_host_path_both_paths_match():
    cfg = C.from_data({"roots": [{"path": ANY_ABSOLUTE}]})
    assert cfg.roots[0].host == cfg.roots[0].folder == ANY_ABSOLUTE


# ---- allowed_hosts: the way out for whoever binds past localhost -----------

def test_a_host_keeps_its_name_and_loses_its_port():
    """The port is not part of a host's identity, and a container publishes on
    a different one than it listens on. Both sides of the comparison in
    `web.host_allowed` go through this, which is why it lives here."""
    assert C.host_only("box.lan:9015") == "box.lan"
    assert C.host_only("BOX.LAN") == "box.lan"
    assert C.host_only("box.lan.") == "box.lan"       # the trailing root dot
    assert C.host_only("  box.lan  ") == "box.lan"


def test_both_spellings_of_ipv6_come_back_the_same():
    """`[::1]:9015` is what a browser sends, `::1` what somebody writes in the
    configuration. Normalizing them differently would refuse the browser that
    is actually looking at the page."""
    assert C.host_only("[::1]:9015") == "::1"
    assert C.host_only("::1") == "::1"
    assert C.host_only("[fe80::1]") == "fe80::1"


def test_a_url_in_allowed_hosts_is_refused_rather_than_never_matched():
    """It would never match anything, and a dashboard that silently refuses to
    write without saying why is the failure this check exists to avoid."""
    for bad in ["http://box.lan", "box.lan/dashboard", "box lan"]:
        with pytest.raises(C.ConfigInvalid) as e:
            C.from_data({"roots": [{"path": ANY_ABSOLUTE}], "allowed_hosts": [bad]})
        assert "allowed_hosts" in str(e.value)


def test_allowed_hosts_defaults_to_nothing_declared():
    """Empty is the right answer for almost everybody: the loopback names are
    accepted by `web.host_allowed` and never need declaring."""
    cfg = C.from_data({"roots": [{"path": ANY_ABSOLUTE}]})

    assert cfg.allowed_hosts == ()


def test_allowed_hosts_reads_a_bare_string_too():
    """One host is the common case, and quoting it alone is what people write."""
    cfg = C.from_data({"roots": [{"path": ANY_ABSOLUTE}], "allowed_hosts": "box.lan:9015"})

    assert cfg.allowed_hosts == ("box.lan",)


def test_the_environment_can_declare_the_hosts_for_a_container(monkeypatch, tmp_path):
    """Unlike the roots, this one IS a flat list of names and not a structure,
    so an environment variable holds it without lying about its shape."""
    path = tmp_path / "config.toml"
    # Single quotes: a TOML literal string, which does not read `\` as an escape.
    # A Windows path in a basic string makes `C:\Users\…` start with `\U`, which
    # TOML reads as a unicode escape and refuses.
    path.write_text(f"[[roots]]\npath = '{ANY_ABSOLUTE}'\n", encoding="utf-8")
    monkeypatch.setenv("FRONTSTEP_ALLOWED_HOSTS", "box.lan, dash.local:9015")

    assert C.load(path).allowed_hosts == ("box.lan", "dash.local")


def test_a_path_on_windows_reads_like_a_windows_path(monkeypatch, tmp_path):
    """`~` is a Unix notation: nothing on Windows expands it, and pasting it
    anywhere there gets an error. The same shortening exists and is spelled
    `%USERPROFILE%`."""
    monkeypatch.setattr(C.os, "name", "nt")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert C._prefix_from(tmp_path / "Documents") == "%USERPROFILE%\\Documents\\"
    assert C._prefix_from(tmp_path) == "%USERPROFILE%\\"


def test_a_path_elsewhere_still_reads_like_one(monkeypatch, tmp_path):
    monkeypatch.setattr(C.os, "name", "posix")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert C._prefix_from(tmp_path / "projects") == "~/projects/"
