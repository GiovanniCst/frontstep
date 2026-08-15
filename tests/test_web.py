"""Route tests: what the HTTP surface does, not what the parser does.

The reason this file exists is `writable`. The configuration has carried that
flag for a while and NOBODY READ IT: the dashboard wrote all the same. Closing
that hole means the refusal has to live in the ROUTES, because an interface is
not a barrier — hiding a button stops nobody from sending the same POST — and a
refusal that lives in a route can only be tested through one.

Fixtures are written in Italian here too, and for the same reason as in
test_core: these are the documents that already exist out there.
"""
import re
from pathlib import Path

import pytest

from frontstep import config as C, core as F, launch as L
from frontstep.web import create_app

DOCUMENTO = """# Progetto x

**Stato:** attivo
**Aggiornato:** 2026-01-05
**Prossimo passo:** Rileggere il §4
**In attesa di:**
**Descrizione:** Riconciliazione dei DDT fra i due gestionali
"""


def _projects(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    (root / "prog").mkdir(parents=True)
    (root / "prog" / "CURRENT_STATUS.md").write_text(DOCUMENTO, encoding="utf-8")
    return root


def _config(tmp_path: Path, writable: bool = True, **extra) -> C.Config:
    root = _projects(tmp_path)
    return C.Config(
        roots=[F.Root(key="projects", folder=str(root), host=str(root),
                      prefix="~/projects/", label="Projects", tags=("work",))],
        writable=writable, **extra,
    )


def _client(tmp_path: Path, writable: bool = True):
    """A client that carries the page's token on every request.

    Not a convenience: it is what makes these tests go through the same door
    the page does. The token is checked in the routes, so a client without it
    would be testing the refusal, not the write — and the tests that DO want
    the refusal ask for it explicitly, below.
    """
    cfg = _config(tmp_path, writable)
    app = create_app(cfg)
    client = app.test_client()
    client.environ_base["HTTP_X_FRONTSTEP_TOKEN"] = app.config["FRONTSTEP_TOKEN"]
    return client, Path(cfg.roots[0].folder)


def _document(root: Path) -> str:
    return (root / "prog" / "CURRENT_STATUS.md").read_text(encoding="utf-8")


# ---- writable = true: the three writes work --------------------------------

def test_closing_a_project_from_the_page(tmp_path):
    client, root = _client(tmp_path)

    r = client.post("/project/projects/prog/status", json={"status": "done"})

    assert r.status_code == 200 and r.get_json()["status"] == F.DONE
    assert "**Stato:** concluso" in _document(root)


def test_writing_the_next_step_from_the_page(tmp_path):
    client, root = _client(tmp_path)

    r = client.post("/project/projects/prog/next-step",
                    json={"next_step": "Chiudere il §5"})

    assert r.status_code == 200 and r.get_json()["next_step"] == "Chiudere il §5"
    assert "**Prossimo passo:** Chiudere il §5" in _document(root)


# ---- the skill: the engine, and the fifth thing this writes ----------------

def test_the_skill_is_installed_where_claude_reads_them(tmp_path, monkeypatch):
    """One file, in another program's folder — the only write that leaves both
    Frontstep's own configuration and the projects."""
    monkeypatch.setattr(F.Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / ".claude").mkdir()
    client, _ = _client(tmp_path)

    r = client.post("/skill/claude")

    assert r.status_code == 201
    skill = tmp_path / ".claude" / "skills" / "frontstep" / "SKILL.md"
    assert skill.is_file()
    assert "CURRENT_STATUS.md" in skill.read_text(encoding="utf-8")


def test_no_claude_folder_means_nothing_is_created(tmp_path, monkeypatch):
    """`~/.claude` missing is how a machine says it does not run Claude Code.
    Creating that folder would be answering a question nobody asked — the page
    hands over a prompt to paste instead."""
    monkeypatch.setattr(F.Path, "home", staticmethod(lambda: tmp_path))
    client, _ = _client(tmp_path)

    r = client.post("/skill/claude")

    assert r.status_code == 404
    assert not (tmp_path / ".claude").exists()


def test_a_read_only_dashboard_does_not_install_the_skill(tmp_path, monkeypatch):
    """`writable = false` reads as "this dashboard does not write". An exception
    for one write is the kind nobody remembers is there."""
    monkeypatch.setattr(F.Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / ".claude").mkdir()
    client, _ = _client(tmp_path, writable=False)

    r = client.post("/skill/claude")

    assert r.status_code == 403
    assert not (tmp_path / ".claude" / "skills").exists()


def test_the_page_offers_the_skill_only_where_it_can_land(tmp_path, monkeypatch):
    """With the folder: a button that writes. Without it: the prompt, and no
    button that could only fail."""
    monkeypatch.setattr(F.Path, "home", staticmethod(lambda: tmp_path))
    client, _ = _client(tmp_path)

    without = client.get("/").get_data(as_text=True)
    (tmp_path / ".claude").mkdir()
    with_folder = client.get("/").get_data(as_text=True)

    assert 'id="do-install-skill"' not in without
    assert "frontstep skill --install claude" in without      # the prompt to paste
    assert 'id="do-install-skill"' in with_folder
    # and both windows are always reachable, whichever the machine is
    for page in (without, with_folder):
        assert 'id="open-skill-claude"' in page and 'id="open-skill-agents"' in page


def test_the_new_project_window_can_drop_agents_md_in(tmp_path):
    """The checkbox: the instructions that make the agent keep the document
    current, in the folder being created."""
    client, root = _client(tmp_path)

    r = client.post("/project/new", json={"root": "projects", "name": "nuovo",
                                          "description": "Che cosa fa e su cosa",
                                          "agents": True})

    assert r.status_code == 201
    assert r.get_json()["agents"]["what"] == "created"
    assert "<!-- frontstep:begin -->" in (root / "nuovo" / "AGENTS.md").read_text()


def test_agents_md_is_not_written_unless_it_is_asked_for(tmp_path):
    client, root = _client(tmp_path)

    client.post("/project/new", json={"root": "projects", "name": "nuovo",
                                      "description": "Che cosa fa e su cosa"})

    assert not (root / "nuovo" / "AGENTS.md").exists()


def test_an_agents_md_that_is_already_there_is_added_to_and_never_replaced(tmp_path):
    """The folder may exist already — "New project" adopts one that has no status
    document — and then AGENTS.md is somebody else's file, written for their
    agent, possibly long before Frontstep turned up.

    So: appended to, and on a second pass only OUR section is rewritten. What
    was in that file is still in it, unchanged, both times."""
    client, root = _client(tmp_path)
    theirs = "# AGENTS\n\nRun `make check` before committing. Never touch vendor/.\n"
    (root / "vecchio").mkdir()
    (root / "vecchio" / "AGENTS.md").write_text(theirs, encoding="utf-8")

    first = client.post("/project/new", json={"root": "projects", "name": "vecchio",
                                              "description": "Progetto che c'era gia",
                                              "agents": True})

    text = (root / "vecchio" / "AGENTS.md").read_text(encoding="utf-8")
    assert first.get_json()["agents"]["what"] == "appended"
    assert text.startswith(theirs.rstrip())          # their file, first and intact
    assert "<!-- frontstep:begin -->" in text

    # And a second time — the way a re-install goes — replaces our section only.
    (root / "vecchio" / "CURRENT_STATUS.md").unlink()
    again = client.post("/project/new", json={"root": "projects", "name": "vecchio",
                                              "description": "Progetto che c'era gia",
                                              "agents": True})
    text = (root / "vecchio" / "AGENTS.md").read_text(encoding="utf-8")

    assert again.get_json()["agents"]["what"] == "replaced"
    assert "Run `make check` before committing." in text
    assert text.count("<!-- frontstep:begin -->") == 1


def test_creating_a_project_from_the_page(tmp_path):
    client, root = _client(tmp_path)

    r = client.post("/project/new", json={"root": "projects", "name": "nuovo",
                                          "description": "Che cosa fa e su cosa"})

    assert r.status_code == 201
    assert (root / "nuovo" / "CURRENT_STATUS.md").is_file()


# ---- writable = false: declared AND enforced -------------------------------

@pytest.mark.parametrize("url, payload", [
    ("/project/projects/prog/status", {"status": "done"}),
    ("/project/projects/prog/next-step", {"next_step": "altro"}),
    ("/project/new", {"root": "projects", "name": "nuovo", "description": "x y z"}),
])
def test_read_only_refuses_every_write(tmp_path, url, payload):
    client, root = _client(tmp_path, writable=False)

    r = client.post(url, json=payload)

    assert r.status_code == 403
    assert "read-only" in r.get_json()["error"]
    # and the disk is untouched: the refusal is not cosmetic
    assert _document(root) == DOCUMENTO
    assert not (root / "nuovo").exists()


def test_read_only_still_reads(tmp_path):
    """A read-only dashboard is a dashboard, not a broken one."""
    client, _ = _client(tmp_path, writable=False)

    assert client.get("/").status_code == 200
    assert client.get("/project/projects/prog").status_code == 200
    assert client.get("/fingerprint").status_code == 200
    assert client.get("/health").get_json()["writable"] is False


def test_read_only_offers_no_command_that_would_be_refused(tmp_path):
    """The routes are the barrier; this is the courtesy. A button whose only
    possible outcome is a 403 is worse than no button."""
    client, _ = _client(tmp_path, writable=False)

    page = client.get("/").get_data(as_text=True)

    assert 'id="open-new"' not in page
    assert "status-btn" not in page
    assert 'class="next-edit"' not in page
    assert "read-only" in page


def test_the_commands_are_there_when_it_can_write(tmp_path):
    """The same assertions the other way round: without this, the test above
    would still pass if the buttons disappeared for some unrelated reason."""
    client, _ = _client(tmp_path)

    page = client.get("/").get_data(as_text=True)

    assert 'id="open-new"' in page
    assert "status-btn" in page
    assert 'class="next-edit"' in page


# ---- the edges of the two write routes -------------------------------------

@pytest.mark.parametrize("url", ["/project/ignota/prog/status",
                                 "/project/ignota/prog/next-step"])
def test_an_unknown_root_is_not_a_project(tmp_path, url):
    client, _ = _client(tmp_path)

    assert client.post(url, json={"status": "done", "next_step": "x"}).status_code == 404


def test_a_next_step_that_is_not_text_is_refused(tmp_path):
    client, root = _client(tmp_path)

    r = client.post("/project/projects/prog/next-step", json={"next_step": ["a"]})

    assert r.status_code == 400
    assert _document(root) == DOCUMENTO


def test_no_next_step_line_no_write(tmp_path):
    client, root = _client(tmp_path)
    (root / "senza").mkdir()
    (root / "senza" / "CURRENT_STATUS.md").write_text(
        "# S\n\n**Stato:** attivo\n", encoding="utf-8")

    r = client.post("/project/projects/senza/next-step", json={"next_step": "x"})

    assert r.status_code == 400
    assert "Next step" in r.get_json()["error"]


def test_no_editor_button_when_the_server_cannot_open_one(tmp_path):
    """The Editor button used to fall back to a `vscode://` link, which names one
    editor for everybody — the opposite of what this button is for. From a page
    the only way to start a program is a registered URI scheme, and none of them
    means "whatever this system opens .md with", so there is nothing honest to
    fall back to: the button goes, and Path stays."""
    cfg = _config(tmp_path, launch=False)
    client = create_app(cfg).test_client()

    page = client.get("/").get_data(as_text=True)

    assert "vscode://" not in page
    assert "open-editor" not in page
    assert "frontstep://projects/prog" in page          # Terminal keeps its handler
    assert "copy-path" in page                          # and the path is still there


def test_the_two_buttons_ask_the_server_when_it_can_open(tmp_path, monkeypatch):
    """The point of the rework: no scheme, no handler to register, and the card
    says which program it will open — which the link it replaces never could."""
    monkeypatch.setattr(L, "detect_terminal",
                        lambda: L.Launcher("Terminal", ("term", L.SLOT)))
    monkeypatch.setattr(L, "detect_editor",
                        lambda: L.Launcher("Kate", ("kate", L.SLOT)))
    client, _ = _client(tmp_path)

    page = client.get("/").get_data(as_text=True)

    assert '<button class="link open-terminal"' in page
    assert '<button class="link open-editor"' in page
    # The program is named in the title. It sits in brackets and after a colon
    # rather than inside the sentence, because a sentence with data on both
    # sides of a preposition cannot be translated as one string.
    assert "(Terminal)" in page and "with Kate" in page
    assert "frontstep://" not in page                   # no handler to register


@pytest.mark.parametrize("argv, says, wants_file", [
    (("kate", L.SLOT), "Open the folder with", False),
    (("gedit", L.SLOT_FILE), "Open the document with", True),
])
def test_the_editor_button_names_what_it_will_actually_open(
        tmp_path, monkeypatch, argv, says, wants_file):
    """It used to say "the folder" and show the folder's path in both cases,
    while handing the editor the FILE — every detection asks for the document.
    Seen on Fedora the first time the button was pressed: the tooltip promised a
    folder and a text editor came up with CURRENT_STATUS.md in it.

    The expected path is BUILT rather than written out: it used to end in
    `/projects/prog`, which is not how that path is spelled on Windows, and the
    tooltip showing a native path there is correct — `config._prefix_from` makes
    the same point about what a card shows.
    """
    monkeypatch.setattr(L, "detect_editor", lambda: L.from_config(argv))
    client, root = _client(tmp_path)
    shows = str(root / "prog" / "CURRENT_STATUS.md") if wants_file else str(root / "prog")

    page = client.get("/").get_data(as_text=True)

    title = re.search(r'class="link open-editor"[^>]*title=\'([^\']+)\'', page).group(1)

    assert title.startswith(says)
    assert title.endswith(shows)


# ---- the attribution: not decoration -------------------------------------
#
# It went missing once already, silently: the translation renamed the CSS class,
# the rule became dead, and a later cleanup deleted the rule as unused. Nothing
# failed, because nothing was watching. This is what watches.

def test_the_attribution_is_on_the_page(tmp_path):
    """NOTICE names the foot of the page as the display where the attribution
    has to appear — which is what section 4(d) of the Apache License asks for in
    a single-page application. It is not a style choice."""
    client, _ = _client(tmp_path)

    page = client.get("/").get_data(as_text=True)

    assert F.AUTHOR in page
    assert F.AUTHOR_MARK in page
    assert "sig-mark" in page


def test_the_attribution_survives_read_only(tmp_path):
    """It is not attached to any feature: a dashboard that writes nothing still
    says who made it."""
    client, _ = _client(tmp_path, writable=False)

    assert F.AUTHOR in client.get("/").get_data(as_text=True)


def test_the_mark_links_to_the_project(tmp_path):
    """The mark carries the link, so the attribution leads somewhere."""
    client, _ = _client(tmp_path)

    page = client.get("/").get_data(as_text=True)

    assert '<a class="sig-mark"' in page
    assert F.PROJECT_URL in page


def test_without_a_url_the_mark_is_still_there_as_text(tmp_path, monkeypatch):
    """A dead link is worse than plain text — and, more to the point, the
    ATTRIBUTION must not depend on the link. Empty the URL and the name stays."""
    monkeypatch.setattr(F, "PROJECT_URL", "")
    client, _ = _client(tmp_path)

    page = client.get("/").get_data(as_text=True)

    assert '<a class="sig-mark"' not in page
    assert '<span class="sig-mark"' in page
    assert F.AUTHOR in page


def test_health_carries_the_attribution_too(tmp_path):
    """The other place a machine can read who is running: useful when the page
    is behind something that rewrites it."""
    client, _ = _client(tmp_path)

    body = client.get("/health").get_json()

    assert body["author"] == F.AUTHOR


# ---- the two gates in front of a page that can write -----------------------
#
# Every test below was first run WITHOUT the defence, against the real routes,
# and every one of them wrote. That is why they are written as the attack and
# not as the feature: what is being checked is that the document on disk is
# still what it was, not that a number came back.

WRITE_URL = "/project/projects/prog/next-step"


def _bare(tmp_path, writable: bool = True):
    """A client with NO token: what everybody else on the machine, and every
    other page in the browser, actually has."""
    cfg = _config(tmp_path, writable)
    return create_app(cfg).test_client(), Path(cfg.roots[0].folder)


def test_a_form_from_another_site_no_longer_writes(tmp_path):
    """The measured one. A `<form>` may be sent cross-origin with no preflight,
    so this request really arrives; before the token it answered 200 and left
    the next step EMPTY, because the form body is not JSON and the route read a
    missing field as an empty string."""
    client, root = _bare(tmp_path)

    r = client.post(WRITE_URL, data={"next_step": "OWNED"},
                    content_type="application/x-www-form-urlencoded")

    assert r.status_code == 403
    assert "**Prossimo passo:** Rileggere il §4" in _document(root)


def test_a_text_plain_post_from_another_site_no_longer_writes(tmp_path):
    """The other content type a cross-origin form can send without a preflight."""
    client, root = _bare(tmp_path)

    r = client.post(WRITE_URL, data='{"next_step": "OWNED"}',
                    content_type="text/plain")

    assert r.status_code == 403
    assert "**Prossimo passo:** Rileggere il §4" in _document(root)


def test_closing_a_project_from_another_site_no_longer_works(tmp_path):
    """The one that did the real damage: it moved the status AND the date."""
    client, root = _bare(tmp_path)

    r = client.post("/project/projects/prog/status", data={"status": "done"},
                    content_type="application/x-www-form-urlencoded")

    assert r.status_code == 403
    assert "**Stato:** attivo" in _document(root)
    assert "**Aggiornato:** 2026-01-05" in _document(root)


def test_a_wrong_token_is_refused(tmp_path):
    """Not just a missing one: a guessed one has to fail too."""
    client, root = _bare(tmp_path)

    r = client.post(WRITE_URL, json={"next_step": "OWNED"},
                    headers={"X-Frontstep-Token": "not-the-token"})

    assert r.status_code == 403
    assert "**Prossimo passo:** Rileggere il §4" in _document(root)


def test_the_refusal_says_which_kind_it_is(tmp_path):
    """The page reads `reason` to tell "the server restarted, reload" apart from
    "this dashboard is read-only", which must NOT reload — it would land on the
    same read-only page for ever."""
    stale, _ = _bare(tmp_path)
    read_only, _ = _client(tmp_path / "ro", writable=False)

    assert stale.post(WRITE_URL, json={}).get_json()["reason"] == "token"
    assert read_only.post(WRITE_URL, json={}).get_json().get("reason") != "token"


def test_each_app_has_its_own_token(tmp_path):
    """It is generated per process and kept in memory: a token from one server
    is worthless against another, which is what makes a restart invalidate
    every page still open."""
    one = create_app(_config(tmp_path))
    two = create_app(_config(tmp_path / "other"))

    assert one.config["FRONTSTEP_TOKEN"] != two.config["FRONTSTEP_TOKEN"]
    assert len(one.config["FRONTSTEP_TOKEN"]) >= 32


def test_the_page_carries_the_token_for_the_script_to_find(tmp_path):
    """The proof is handed over by being rendered INTO the page: reading it is
    what a cross-origin script cannot do."""
    cfg = _config(tmp_path)
    app = create_app(cfg)

    page = app.test_client().get("/").get_data(as_text=True)

    assert f'<meta name="frontstep-token" content="{app.config["FRONTSTEP_TOKEN"]}">' in page


# ---- the Host check: DNS rebinding -----------------------------------------

def test_a_rebound_name_cannot_write(tmp_path):
    """Rebinding makes an attacker's page same-origin with this one, so the
    token stops protecting: the name the browser dialled is what does."""
    client, root = _client(tmp_path)

    r = client.post(WRITE_URL, json={"next_step": "OWNED"},
                    headers={"Host": "evil.example"})

    assert r.status_code == 403
    assert "**Prossimo passo:** Rileggere il §4" in _document(root)


def test_a_rebound_name_cannot_read_either(tmp_path):
    """Reads too. The page lists every project on the machine by name, and that
    is somebody's client list."""
    client, _ = _client(tmp_path)

    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/project/projects/prog",
                      headers={"Host": "evil.example"}).status_code == 403


def test_the_refusal_names_the_key_that_fixes_it(tmp_path):
    """It can land in front of a person who typed the address, so it says what
    to do rather than only that it will not."""
    client, _ = _client(tmp_path)

    body = client.get("/", headers={"Host": "box.lan"}).get_data(as_text=True)

    assert "allowed_hosts" in body and "box.lan" in body


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:9015", "localhost",
                                  "localhost:9015", "[::1]:9015", "::1"])
def test_the_loopback_names_are_always_allowed(tmp_path, host):
    """Whatever the configuration says. These are the names that mean "this
    machine" and cannot be made to mean anything else — with or without a port,
    and in either IPv6 spelling."""
    client, _ = _client(tmp_path)

    assert client.get("/", headers={"Host": host}).status_code == 200


def test_a_declared_host_is_allowed(tmp_path):
    """The way out for whoever binds past localhost: declare the name."""
    cfg = _config(tmp_path, allowed_hosts=("box.lan",))
    app = create_app(cfg)
    client = app.test_client()
    client.environ_base["HTTP_X_FRONTSTEP_TOKEN"] = app.config["FRONTSTEP_TOKEN"]

    assert client.get("/", headers={"Host": "box.lan:9015"}).status_code == 200
    assert client.post(WRITE_URL, json={"next_step": "from the LAN"},
                       headers={"Host": "box.lan:9015"}).status_code == 200


def test_declaring_one_host_does_not_open_the_others(tmp_path):
    """`allowed_hosts` adds a name, it does not turn the check off."""
    cfg = _config(tmp_path, allowed_hosts=("box.lan",))
    client = create_app(cfg).test_client()

    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403


def test_a_request_with_no_host_at_all_is_refused(tmp_path):
    """HTTP/1.1 requires it and every browser sends it. Allowing the request
    that omits it would let anyone turn the check off by leaving it out."""
    client, _ = _client(tmp_path)

    r = client.get("/", environ_overrides={"HTTP_HOST": ""})

    assert r.status_code == 403


def test_health_still_answers_the_container_probe(tmp_path):
    """The compose healthcheck calls it on 127.0.0.1 and carries no token: a
    liveness probe that the defence breaks is a container that restarts for
    ever."""
    client, _ = _bare(tmp_path)

    assert client.get("/health", headers={"Host": "127.0.0.1:9015"}).status_code == 200


def test_a_write_that_fails_is_not_reported_as_a_missing_line(tmp_path, monkeypatch):
    """Two different answers used to be the same 400: "there is no such line in
    your header" and "I could not write to your disk". The first sends somebody
    to check a header that is perfect."""
    client, root = _client(tmp_path)

    def refuse(*a, **k):
        raise OSError(13, "Permission denied")
    monkeypatch.setattr(F.os, "replace", refuse)

    r = client.post("/project/projects/prog/status", json={"status": "done"})

    assert r.status_code == 500
    assert "could not write" in r.get_json()["error"]
