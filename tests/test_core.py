"""Parser tests: anchored to real files written by the test, not to mocks.

The sore point is tolerance — a status document written by hand, with a
different casing or with no header at all, must not break anything.

Some fixtures are written in Italian on purpose: those are the documents the
bilingual parser has to keep reading, and a translated fixture would stop
testing that.
"""
import datetime as dt
import stat
from pathlib import Path

import pytest

import frontstep
from frontstep import core as F


def write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


def a_root(folder="", host="/host", key="projects", tags=("work",),
        prefix="~/projects/") -> F.Root:
    """The work root, which is the one for tests that are not about roots.
    A test that tries two of them passes its own."""
    return F.Root(key=key, folder=str(folder), host=host,
                    tags=tuple(tags), prefix=prefix)


COMPLETO = """# CURRENT_STATUS — progetto x

**Stato:** in-attesa
**Aggiornato:** 2026-08-01
**Prossimo passo:** Rileggere il piano e chiudere il §4
**In attesa di:** Robin — conferma sul rilievo 2b

## Altro
corpo libero
"""


def test_a_complete_header(tmp_path):
    write(tmp_path / "progetto_x", "CURRENT_STATUS.md", COMPLETO)
    f = F.read_project(tmp_path / "progetto_x", a_root(host="/host/projects"))

    assert f.status == F.WAITING
    assert f.updated == dt.date(2026, 8, 1)
    assert f.next_step == "Rileggere il piano e chiudere il §4"
    assert f.waiting_for == "Robin — conferma sul rilievo 2b"
    assert f.title == "CURRENT_STATUS — progetto x"
    assert f.status_file == "/host/projects/progetto_x/CURRENT_STATUS.md"
    assert f.has_header and f.canonical_casing


def test_no_header_does_not_break(tmp_path):
    write(tmp_path / "vecchio", "CURRENT_STATUS.md", "# Vecchio\n\nnessun header qui\n")
    f = F.read_project(tmp_path / "vecchio", a_root(host="/host"))

    assert f.status == F.UNDECLARED
    assert f.has_header is False
    assert f.updated is None
    # with no declared date the silence is measured on the mtime, not lost
    assert f.days_silent is not None


def test_empty_fields_stay_empty(tmp_path):
    write(tmp_path / "p", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** concluso\n**Aggiornato:** 2026-04-02\n"
           "**Prossimo passo:**\n**In attesa di:**\n")
    f = F.read_project(tmp_path / "p", a_root(host="/host"))

    assert f.status == F.DONE
    assert f.next_step == ""
    assert f.waiting_for == ""


def test_non_canonical_casing_is_read_and_flagged(tmp_path, case_sensitive_fs):
    write(tmp_path / "kb", "current_status.md", COMPLETO)
    f = F.read_project(tmp_path / "kb", a_root(host="/host"))

    assert f.status == F.WAITING
    assert f.canonical_casing is False
    assert f.status_filename == "current_status.md"


def test_the_first_updated_wins(tmp_path):
    """I documenti lunghi ripetono '**Aggiornato:**' nel corpo: conta l'header."""
    write(tmp_path / "p", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-11\n"
           "**Prossimo passo:** x\n**In attesa di:**\n\n"
           "**Aggiornato:** 2026-01-01 sera — riga vecchia nel corpo\n")
    assert F.read_project(tmp_path / "p", a_root(host="/host")).updated == dt.date(2026, 8, 11)


@pytest.mark.parametrize("written,expected", [
    # Italian: these are the documents already written, and they have to keep working
    ("attivo", F.ACTIVE), ("Attivo", F.ACTIVE), ("in attesa", F.WAITING),
    ("IN-ATTESA", F.WAITING), ("sospeso", F.PAUSED), ("Concluso", F.DONE),
    ("chiuso", F.DONE),
    # English: the project's canonical language
    ("active", F.ACTIVE), ("Active", F.ACTIVE), ("waiting", F.WAITING),
    ("blocked", F.WAITING), ("on hold", F.WAITING), ("paused", F.PAUSED),
    ("suspended", F.PAUSED), ("done", F.DONE), ("Completed", F.DONE),
    ("shipped", F.DONE),
    # what cannot be understood does not become an invented status
    ("boh", F.UNDECLARED),
])
def test_status_aliases(tmp_path, written, expected):
    d = tmp_path / ("p_" + written.replace(" ", "_").replace("-", "_").lower())
    write(d, "CURRENT_STATUS.md", f"# P\n\n**Stato:** {written}\n**Aggiornato:** 2026-08-01\n")
    assert F.read_project(d, a_root(host="/host")).status == expected


def test_an_unreadable_date_does_not_raise(tmp_path):
    write(tmp_path / "p", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** attivo\n**Aggiornato:** boh, non lo so\n")
    f = F.read_project(tmp_path / "p", a_root(host="/host"))
    assert f.status == F.ACTIVE and f.updated is None


def test_a_folder_with_no_status_file(tmp_path):
    (tmp_path / "niente").mkdir()
    assert F.read_project(tmp_path / "niente", a_root(host="/host")) is None


# ---- the git remote ------------------------------------------------------------

def _git_config(folder: Path, url: str):
    (folder / ".git").mkdir(parents=True, exist_ok=True)
    (folder / ".git" / "config").write_text(
        f'[core]\n\trepositoryformatversion = 0\n[remote "origin"]\n\turl = {url}\n',
        encoding="utf-8")


def test_the_remote_url_is_clean(tmp_path):
    d = tmp_path / "p"
    write(d, "CURRENT_STATUS.md", COMPLETO)
    _git_config(d, "https://git.example.com/octocat/hello.git")
    assert F.read_project(d, a_root(host="/host")).remote_url == "https://git.example.com/octocat/hello"


def test_a_token_in_the_remote_never_reaches_the_page(tmp_path):
    """A remote with credentials inside the URL really does turn up in real
    repositories, and the dashboard must not republish it: the link would land
    on the page with the secret in it, visible to anyone looking at the screen."""
    d = tmp_path / "p"
    write(d, "CURRENT_STATUS.md", COMPLETO)
    _git_config(d, "https://user:not-a-real-token@git.example.com/octocat/hello.git")
    url = F.read_project(d, a_root(host="/host")).remote_url

    assert url == "https://git.example.com/octocat/hello"
    assert "not-a-real-token" not in url and "@" not in url


def test_no_git_no_link(tmp_path):
    write(tmp_path / "p", "CURRENT_STATUS.md", COMPLETO)
    assert F.read_project(tmp_path / "p", a_root(host="/host")).remote_url == ""


# ---- the optional external index ---------------------------------------------------------

INDEX = """# Indice dei progetti

## Feedback
- [Qualcosa](nota_x.md) — non e' un progetto

## Progetti — attivi
- **attivo** — [Segnalazioni](progetto_s.md) — raccolta segnalazioni in `~/projects/segnalazioni/`
- **attivo, da eseguire** — [Manutenzione](progetto_m.md) — da fare (`~/projects/manutenzione/`)

## Progetti — sospesi
- **sospeso 2026-04-23** — [Costi](progetto_c.md) — piano in `~/projects/revisione_costi/`
"""


def test_the_external_index(tmp_path):
    p = tmp_path / "MEMORY.md"
    p.write_text(INDEX, encoding="utf-8")
    entries = F.read_index(p)

    assert set(entries) == {"segnalazioni", "manutenzione", "revisione_costi"}
    assert entries["segnalazioni"]["status"] == F.ACTIVE
    assert entries["manutenzione"]["status"] == F.ACTIVE        # "attivo, da eseguire"
    assert entries["revisione_costi"]["status"] == F.PAUSED     # "sospeso 2026-04-23"


def test_an_index_reference_works_whatever_folder_you_keep_projects_in(tmp_path):
    """⚠️ The pattern used to require `~/projects/` — one person's layout. For
    anyone who keeps their projects anywhere else, the index matched nothing and
    said nothing about it. The last segment is the project, the prefix is theirs.

    A command in backticks is not a path, and must not become a project.
    """
    p = tmp_path / "INDEX.md"
    p.write_text(
        "## Projects — active\n"
        "- **active** — [One](o.md) — in `~/projects/one/`\n"
        "- **active** — [Two](t.md) — in `~/code/two/`\n"
        "- **active** — [Three](h.md) — in `/srv/repos/three/`\n"
        "- **active** — [Four](f.md) — in `%USERPROFILE%/work/four/`\n"
        "- **active** — [Command](c.md) — started with `frontstep serve`\n",
        encoding="utf-8")

    entries = F.read_index(p)

    assert set(entries) == {"one", "two", "three", "four"}
    assert all(entries[name]["folder"] == name for name in entries)


def test_a_reference_to_a_file_does_not_become_a_folder(tmp_path):
    """Some projects live in a plan, not in a folder: the project takes its name
    from the title, not from the file name."""
    p = tmp_path / "MEMORY.md"
    p.write_text(
        "## Progetti — sospesi\n"
        "- **sospeso 2026-04-23** — [Migrazione](progetto_l.md) — "
        "piano in `~/projects/PIANO_MIGRAZIONE.md`\n",
        encoding="utf-8")
    entries = F.read_index(p)

    assert set(entries) == {"Migrazione"}
    assert entries["Migrazione"]["folder"] == ""
    assert entries["Migrazione"]["status"] == F.PAUSED


def test_the_section_status_is_the_default(tmp_path):
    """A line with no explicit status inherits the one of its section title."""
    p = tmp_path / "MEMORY.md"
    p.write_text(
        "## Progetti — sospesi\n"
        "- **boh** — [X](project_x.md) — sta in `~/projects/xxx/`\n",
        encoding="utf-8")
    assert F.read_index(p)["xxx"]["status"] == F.PAUSED


def test_a_missing_index_does_not_break(tmp_path):
    assert F.read_index(tmp_path / "non_esiste.md") == {}


# ---- scanning and ordering ----------------------------------------------

def test_the_status_file_beats_the_index(tmp_path):
    """If the folder has a status document, that document is the truth."""
    root = tmp_path / "projects"
    write(root / "segnalazioni", "CURRENT_STATUS.md",
           "# IT\n\n**Stato:** sospeso\n**Aggiornato:** 2026-07-01\n")
    mem = tmp_path / "MEMORY.md"
    mem.write_text(INDEX, encoding="utf-8")

    projects = F.scan([a_root(root, host="/host")], str(mem))
    it = [f for f in projects if f.name == "segnalazioni"][0]

    assert it.status == F.PAUSED          # from the file, not "attivo" from the index
    assert it.has_status_file is True
    # the other two index entries still get in, as cards without a document
    without = {f.name for f in projects if not f.has_status_file}
    assert without == {"manutenzione", "revisione_costi"}


def test_order_by_section_then_silence(tmp_path):
    root = tmp_path / "projects"
    for name, status, data in [
        ("chiuso", "concluso", "2026-08-10"),
        ("fermo", "attivo", "2026-01-01"),
        ("fresco", "attivo", "2026-08-10"),
        ("aspetta", "in-attesa", "2026-08-10"),
        ("pausa", "sospeso", "2026-08-10"),
    ]:
        write(root / name, "CURRENT_STATUS.md",
               f"# {name}\n\n**Stato:** {status}\n**Aggiornato:** {data}\n")

    names = [f.name for f in F.scan([a_root(root, host="/h")], str(tmp_path / "no.md"))]
    # OPEN first, most recent to most silent: "waiting on others"
    # `waiting` is not a section of its own, so it sits among the active ones by
    # its date rather than behind all of them. Then paused, then done at the end.
    assert names == ["aspetta", "fresco", "fermo", "pausa", "chiuso"]


def test_waiting_belongs_to_the_open_section(tmp_path):
    """A project blocked on someone else is still an open project: giving it a
    section of its own breaks the only reading that matters, most recent to most
    silent. You recognise it by the status on the card, not by the section."""
    root = tmp_path / "projects"
    for name, status in [("mio", "attivo"), ("suo", "in-attesa"), ("pausa", "sospeso")]:
        write(root / name, "CURRENT_STATUS.md",
               f"# {name}\n\n**Stato:** {status}\n**Aggiornato:** 2026-08-10\n")

    gruppi = F.group_into_sections(F.scan([a_root(root, host="/h")], str(tmp_path / "no.md")))
    sezioni = {key: [f.name for f in members] for key, _, _, members in gruppi}
    assert sezioni["open"] == ["mio", "suo"]
    assert sezioni["paused"] == ["pausa"]
    assert F.WAITING not in sezioni
    # the status stays distinct: it is what colours the card and drives the filter
    stati = {f.name: f.status for f in F.scan([a_root(root, host="/h")], str(tmp_path / "no.md"))}
    assert stati["suo"] == F.WAITING


def test_projects_with_no_date_go_last_in_their_section(tmp_path):
    """Sorting by most recent, "no date" cannot count as zero days: a project that
    only exists in the index would land on top, as if it had been worked on this
    morning."""
    root = tmp_path / "projects"
    write(root / "datato", "CURRENT_STATUS.md",
           "# a\n\n**Stato:** attivo\n**Aggiornato:** 2026-01-01\n")
    mem = tmp_path / "MEMORY.md"
    mem.write_text("## Progetti — attivi\n"
                   "- **attivo** — [Senza data](p.md) — sta in `~/projects/orfano/`\n",
                   encoding="utf-8")

    projects = F.scan([a_root(root, host="/h")], str(mem))
    assert [f.name for f in projects] == ["datato", "orfano"]
    assert [f.days_silent for f in projects][1] is None


def _timeline(tmp_path, root, stale_days=7):
    return F.silence_line(
        F.scan([a_root(root, host="/h")], str(tmp_path / "no.md")), stale_days)


def test_the_silence_line_keeps_only_open_projects(tmp_path):
    """Only the projects of the Open section belong on the line.

    The silence of a closed or paused project is not a signal: those are stopped
    by a decision already taken. Keeping them stretches the axis and pushes the
    live projects against the right edge, and those are the only thing the line
    has to show.
    """
    root = tmp_path / "projects"
    oggi = dt.date.today()
    write(root / "vecchio", "CURRENT_STATUS.md",
           f"# a\n\n**Stato:** attivo\n**Aggiornato:** {oggi - dt.timedelta(days=100)}\n")
    write(root / "oggi", "CURRENT_STATUS.md",
           f"# b\n\n**Stato:** attivo\n**Aggiornato:** {oggi}\n")
    write(root / "atteso", "CURRENT_STATUS.md",
           f"# d\n\n**Stato:** in-attesa\n**Aggiornato:** {oggi}\n")
    write(root / "chiuso", "CURRENT_STATUS.md",
           f"# c\n\n**Stato:** concluso\n**Aggiornato:** {oggi}\n")
    # Three years silent: on the axis it would rescale everyone else by itself.
    write(root / "fermo", "CURRENT_STATUS.md",
           f"# e\n\n**Stato:** sospeso\n**Aggiornato:** {oggi - dt.timedelta(days=1095)}\n")

    linea = _timeline(tmp_path, root)
    tl = {t["name"]: t for t in linea["ticks"]}

    assert set(tl) == {"vecchio", "oggi", "atteso"}
    assert tl["vecchio"]["left"] == 0.0     # the most silent, hard left
    assert tl["oggi"]["left"] == 100.0      # oggi, tutto a destra
    # The axis reaches the most silent OPEN one, not a paused three-year-old.
    assert linea["max_days"] == 100


def test_the_log_scale_does_not_squash_the_recent(tmp_path):
    """Why the scale is not linear: one very old project must not pile all the
    others against the right edge."""
    root = tmp_path / "projects"
    oggi = dt.date.today()
    for name, days in [("outlier", 365), ("tre", 3), ("dieci", 10), ("trenta", 30)]:
        write(root / name, "CURRENT_STATUS.md",
               f"# {name}\n\n**Stato:** attivo\n"
               f"**Aggiornato:** {oggi - dt.timedelta(days=days)}\n")

    tl = {t["name"]: t["left"] for t in _timeline(tmp_path, root)["ticks"]}

    # su scala lineare "tre" starebbe al 99,2%: tutto ammassato a destra
    assert tl["tre"] < 80, tl
    # the real order holds: older = further left
    assert tl["outlier"] < tl["trenta"] < tl["dieci"] < tl["tre"]


def test_grid_only_below_the_max_and_without_the_threshold(tmp_path):
    """A 365d tick on an axis that stops at 40 would be off the axis. And the
    threshold is not repeated: the edge of its zone already marks it."""
    root = tmp_path / "projects"
    oggi = dt.date.today()
    write(root / "p", "CURRENT_STATUS.md",
           f"# p\n\n**Stato:** attivo\n**Aggiornato:** {oggi - dt.timedelta(days=40)}\n")

    assert [g["days"] for g in _timeline(tmp_path, root, stale_days=7)["grid"]] == [30]
    assert [g["days"] for g in _timeline(tmp_path, root, stale_days=30)["grid"]] == [7]
    assert all(0 <= g["left"] <= 100
               for g in _timeline(tmp_path, root)["grid"])


def test_an_empty_timeline_does_not_break(tmp_path):
    root = tmp_path / "projects"
    write(root / "chiuso", "CURRENT_STATUS.md",
           "# c\n\n**Stato:** concluso\n**Aggiornato:** 2026-01-01\n")
    tl = _timeline(tmp_path, root)
    assert tl["ticks"] == [] and tl["grid"] == []


def test_header_behind_the_file(tmp_path):
    """The file was touched after the date declared: the header is behind."""
    d = tmp_path / "p"
    p = write(d, "CURRENT_STATUS.md",
               "# P\n\n**Stato:** attivo\n**Aggiornato:** 2026-01-01\n")
    import os
    recente = dt.datetime(2026, 6, 1).timestamp()
    os.utime(p, (recente, recente))

    assert F.read_project(d, a_root(host="/h")).header_behind is True


# ---- the derived description --------------------------------------------------
# The description is never written by hand anywhere: it is derived from the
# document. What is pinned here is WHAT counts as one and what does not.

def test_description_prefers_the_section_that_explains():
    text = """# Progetto

**Stato:** attivo
**Aggiornato:** 2026-08-01

Questa riga sta prima ed e' prosa, ma non spiega di cosa si tratta davvero.

## Obiettivo
Riordinare i 54 job schedulati sul server, decidendo per ognuno se tenerlo.
"""
    d = F.derived_description(text.split("\n"))
    assert d.startswith("Riordinare i 54 job")


def test_description_takes_the_whole_paragraph_not_the_first_line():
    """A wrapped paragraph, cut by lines, starts halfway through a clause and
    reads as nonsense."""
    text = """# Progetto

## Cos'e'
Vista aggregata di tutti i fronti aperti,
che risponde a una domanda sola.
"""
    assert F.derived_description(text.split("\n")) == (
        "Vista aggregata di tutti i fronti aperti, che risponde a una domanda sola."
    )


def test_description_ignores_field_lines_and_dates():
    """"Last updated: ..." talks about the document, not the project — and the date
    is already on the card."""
    text = """# Progetto

**Stato:** attivo
**Aggiornato:** 2026-08-01
**Date**: 2026-03-11

Ultimo aggiornamento: 2026-06-05, fix installato e testato in produzione.

App Flask per prenotare le sale riunioni, una pagina per piano.
"""
    assert F.derived_description(text.split("\n")).startswith("App Flask per prenotare")


def test_description_skips_tables_lists_and_code():
    text = """# Progetto

| Colonna | Altra colonna che allunga la riga oltre il minimo |
|---|---|
| a | b |

- un elenco puntato non e' una descrizione del progetto, e' un dettaglio

```
un blocco di codice lungo abbastanza da superare la soglia dei caratteri
```

> una citazione che pure supera la soglia dei venticinque caratteri

Procedura per spostare le casse dal deposito al negozio e rivenderle.
"""
    assert F.derived_description(text.split("\n")) == (
        "Procedura per spostare le casse dal deposito al negozio e rivenderle."
    )


def test_description_is_empty_when_there_is_no_prose():
    text = """# Progetto

**Stato:** attivo

## Tabelle
| a | b |
|---|---|

- solo elenchi
"""
    assert F.derived_description(text.split("\n")) == ""


def test_description_is_cut_at_a_sentence_end():
    lunga = "Prima frase che sta comodamente dentro il limite previsto. " + "coda " * 60
    text = "# P\n\n## Obiettivo\n" + lunga + "\n"
    d = F.derived_description(text.split("\n"))
    assert d == "Prima frase che sta comodamente dentro il limite previsto."


def test_the_description_reaches_the_card(tmp_path):
    write(tmp_path / "prog", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** attivo\n\n## Cos'e'\n"
           "Applicazione che riconcilia le ricevute del mese con i movimenti di cassa.\n")
    f = F.read_project(tmp_path / "prog", a_root(host="/host/projects"))
    assert f.description.startswith("Applicazione che riconcilia")
    assert f.folder == "prog"


def test_description_stops_where_the_list_starts():
    """A list glued to the paragraph with no blank line closes it: the entries of
    that list are not the project's description."""
    text = """# Progetto

App Flask di rilevamento anomalie sulle letture mensili:
- **Anomalie di lettura**: consumo del mese corrente sotto quello precedente
- **Anomalie di quantita**: scostamenti oltre la soglia dichiarata
"""
    assert F.derived_description(text.split("\n")) == (
        "App Flask di rilevamento anomalie sulle letture mensili"
    )


def test_the_continuation_of_a_list_is_not_a_description():
    """After a wrapped list entry, the continuation line is not a new paragraph:
    taking it would give a sentence starting from the middle."""
    text = """# Progetto

- prima entry dell'elenco che va a capo perche' e' lunga
  e questa e' la sua continuazione, che non e' una descrizione

Questa invece e' la prima vera prosa del documento, dopo la riga vuota.
"""
    assert F.derived_description(text.split("\n")).startswith("Questa invece")


def test_the_declared_description_beats_the_derived_one(tmp_path):
    """Where the field is there, it is the source: deriving from the text is only
    the safety net for documents that do not have it yet."""
    write(tmp_path / "prog", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** attivo\n**Descrizione:** App Flask che riconcilia i movimenti "
           "di cassa con le ricevute del mese.\n\n"
           "## Cos'e'\nQuesta prosa NON deve vincere sul campo dichiarato.\n")
    f = F.read_project(tmp_path / "prog", a_root(host="/h"))

    assert f.description.startswith("App Flask che riconcilia")
    assert f.description_derived is False


def test_without_the_field_it_falls_back_to_the_text(tmp_path):
    write(tmp_path / "prog", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** attivo\n\n## Obiettivo\n"
           "Riordinare le attivita' pianificate, una per una, decidendo cosa tenere.\n")
    f = F.read_project(tmp_path / "prog", a_root(host="/h"))

    assert f.description.startswith("Riordinare le attivita")
    assert f.description_derived is True


# ---- the whole document, behind the card ----------------------------------

def test_the_document_is_read_again_now(tmp_path):
    """No cache: a card gets opened precisely while the file is changing."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", "# P\n\nprima version\n")

    assert "prima version" in F.document("prog", str(root), "/h")["text"]
    p.write_text("# P\n\nseconda version\n", encoding="utf-8")
    doc = F.document("prog", str(root), "/h")

    assert "seconda version" in doc["text"]
    assert doc["name"] == "prog"
    assert doc["host_path"] == "/h/prog/CURRENT_STATUS.md"


@pytest.mark.parametrize("base, expected", [
    ("/home/me/projects",      "/home/me/projects/prog/CURRENT_STATUS.md"),
    ("/home/me/projects/",     "/home/me/projects/prog/CURRENT_STATUS.md"),
    ("/",                      "/prog/CURRENT_STATUS.md"),
    ("C:\\Users\\me",          "C:\\Users\\me\\prog\\CURRENT_STATUS.md"),
    ("C:\\Users\\me\\",        "C:\\Users\\me\\prog\\CURRENT_STATUS.md"),
    ("\\\\srv\\share",         "\\\\srv\\share\\prog\\CURRENT_STATUS.md"),
])
def test_a_host_path_is_joined_the_way_that_host_writes_paths(base, expected):
    """⚠️ Found on a Windows runner: the folder handed to a terminal came out
    `C:\\Users\\…\\projects/prog`, mixed separators, because this was an f-string
    with a `/` in it.

    The shape is the BASE's, never this machine's, and that distinction is the
    reason `os.path.join` cannot be used: the host path is the path on the
    machine of whoever is looking, which in a container may be Windows while
    this process runs on Linux. So these cases all pass on every system —
    including the trailing separator and a lone `/`, which the hand-written
    `rstrip` got wrong.
    """
    assert F.host_join(base, "prog", "CURRENT_STATUS.md") == expected


def test_the_document_reads_the_wrong_casing_too(tmp_path, case_sensitive_fs):
    root = tmp_path / "projects"
    write(root / "prog", "current_status.md", "# P\n\ncorpo\n")
    doc = F.document("prog", str(root), "/h")

    assert doc["file"] == "current_status.md"
    assert "corpo" in doc["text"]


@pytest.mark.parametrize("name", [
    "..", "../etc", "prog/../..", "/etc", "", ".ssh", "sotto/prog",
])
def test_the_document_never_leaves_its_root(tmp_path, name):
    """`name` comes from the URL: it is a label, not a path."""
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", "# P\n")
    write(tmp_path, "segreto.md", "non si legge")

    assert F.document(name, str(root), "/h") is None


def test_the_document_does_not_follow_a_symlink_out_of_the_root(tmp_path):
    """The check comes after resolve(), not on the string: a symlink pointing
    outside is a clean path that leads where it must not."""
    root = tmp_path / "projects"
    root.mkdir(parents=True)
    fuori = tmp_path / "fuori"
    write(fuori, "CURRENT_STATUS.md", "# roba altrui\n")
    (root / "scorciatoia").symlink_to(fuori, target_is_directory=True)

    assert F.document("scorciatoia", str(root), "/h") is None


def test_no_document_when_the_folder_has_no_status_file(tmp_path):
    root = tmp_path / "projects"
    (root / "vuota").mkdir(parents=True)

    assert F.document("vuota", str(root), "/h") is None
    assert F.document("inesistente", str(root), "/h") is None


# ---- the first write: the "Close" button -------------------------------

ORIGINALE = """# CURRENT_STATUS — progetto x

**Stato:** attivo
**Aggiornato:** 2026-01-05
**Prossimo passo:** Rileggere il §4
**In attesa di:**
**Descrizione:** Riconciliazione dei DDT fra i due gestionali

## Corpo

Testo con **Stato:** citato dentro il corpo, che NON e' l'header.

| a | b |
|---|---|
| 1 | 2 |
"""


def test_closing_writes_status_and_date(tmp_path):
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    result = F.set_status("prog", str(root), "concluso", today=dt.date(2026, 8, 13))
    after = p.read_text(encoding="utf-8")

    assert result == {"name": "prog", "status": F.DONE, "updated": "2026-08-13"}
    assert "**Stato:** concluso" in after
    assert "**Aggiornato:** 2026-08-13" in after
    assert F.read_project(root / "prog", a_root(host="/h")).status == F.DONE


def test_only_the_two_header_lines_are_rewritten(tmp_path):
    """The rest of the document goes back to disk as it was: it is somebody else's
    file, and the app touches those two lines only."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    F.set_status("prog", str(root), "concluso", today=dt.date(2026, 8, 13))
    before = ORIGINALE.split("\n")
    after = p.read_text(encoding="utf-8").split("\n")

    assert len(before) == len(after)
    cambiate = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert cambiate == [2, 3]                      # only Stato and Aggiornato
    # the "**Stato:**" quoted in the body is not the header, and stays put
    assert "Testo con **Stato:** citato dentro il corpo" in "\n".join(after)


def test_reopening_goes_back_to_active(tmp_path):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    F.set_status("prog", str(root), "concluso", today=dt.date(2026, 8, 13))
    F.set_status("prog", str(root), "attivo", today=dt.date(2026, 8, 14))

    f = F.read_project(root / "prog", a_root(host="/h"))
    assert f.status == F.ACTIVE and f.updated == dt.date(2026, 8, 14)


def test_with_no_status_line_nothing_is_written(tmp_path):
    """A document with no header does not get "fixed" by inventing one for it."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", "# P\n\nnessun header qui\n")

    assert F.set_status("prog", str(root), "concluso") is None
    assert p.read_text(encoding="utf-8") == "# P\n\nnessun header qui\n"


@pytest.mark.parametrize("name", ["..", "../altro", "/etc", ""])
def test_nothing_is_written_outside_the_root(tmp_path, name):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    fuori = write(tmp_path / "altro", "CURRENT_STATUS.md", ORIGINALE)

    assert F.set_status(name, str(root), "concluso") is None
    assert fuori.read_text(encoding="utf-8") == ORIGINALE


def test_a_made_up_status_does_not_pass(tmp_path):
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    assert F.set_status("prog", str(root), "archiviato") is None
    assert F.set_status("prog", str(root), F.UNDECLARED) is None
    assert p.read_text(encoding="utf-8") == ORIGINALE


def test_no_temporary_file_is_left_behind(tmp_path):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    F.set_status("prog", str(root), "concluso")

    assert [p.name for p in (root / "prog").iterdir()] == ["CURRENT_STATUS.md"]


def test_pausing_and_resuming(tmp_path):
    """Pause works exactly like Close: it moves the same switch."""
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    assert F.set_status("prog", str(root), "sospeso",
                           today=dt.date(2026, 8, 13))["status"] == F.PAUSED
    assert F.read_project(root / "prog", a_root(host="/h")).status == F.PAUSED

    F.set_status("prog", str(root), "attivo", today=dt.date(2026, 8, 14))
    assert F.read_project(root / "prog", a_root(host="/h")).status == F.ACTIVE


def test_a_paused_project_can_be_closed_directly(tmp_path):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    F.set_status("prog", str(root), "sospeso")
    F.set_status("prog", str(root), "concluso")
    assert F.read_project(root / "prog", a_root(host="/h")).status == F.DONE


def test_three_sections_and_undeclared_sits_among_the_open(tmp_path):
    """The sections are also the three filters: if a project fell outside these
    three, no button could show it. A broken header is a diagnosis of the
    document, not a status of the work: the project stays open."""
    root = tmp_path / "projects"
    write(root / "attivo", "CURRENT_STATUS.md",
           "# a\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n")
    write(root / "aspetta", "CURRENT_STATUS.md",
           "# b\n\n**Stato:** in-attesa\n**Aggiornato:** 2026-08-09\n")
    write(root / "rotto", "CURRENT_STATUS.md", "# c\n\nnessun header qui\n")
    write(root / "pausa", "CURRENT_STATUS.md",
           "# d\n\n**Stato:** sospeso\n**Aggiornato:** 2026-08-10\n")
    write(root / "chiuso", "CURRENT_STATUS.md",
           "# e\n\n**Stato:** concluso\n**Aggiornato:** 2026-08-10\n")

    tutti = F.scan([a_root(root, host="/h")], str(tmp_path / "no.md"))
    gruppi = F.group_into_sections(tutti)

    assert [key for key, _, _, _ in gruppi] == ["open", "paused", "closed"]
    assert [et for _, et, _, _ in gruppi] == ["Open", "Paused", "Closed"]
    aperti = {f.name for _, _, _, members in gruppi[:1] for f in members}
    assert aperti == {"attivo", "aspetta", "rotto"}
    # every project lands in one section and one only
    assert sum(len(m) for _, _, _, m in gruppi) == len(tutti)
    # the status stays distinct: it is the section that gathers three of them
    assert {f.name: f.status for f in tutti}["rotto"] == F.UNDECLARED


# ---- the version: one source, and nobody left behind -------------------

def test_the_version_has_one_source():
    """`__init__.py` is the source: the package, the page and pyproject.toml all
    read it from there. Declaring it in two places means sooner or later
    declaring two different ones, right when you need to trust it."""
    assert F.VERSION == frontstep.__version__
    assert F.VERSION, "la version non puo' essere vuota"

    root = Path(__file__).resolve().parent.parent
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    # hatchling reads the version from __init__.py: if someone wrote it by
    # hand in here, they would be two sources again.
    assert 'dynamic = ["version"]' in pyproject
    assert 'path = "src/frontstep/__init__.py"' in pyproject


def test_the_signature_says_version_repo_and_commit():
    """The repository name is declared in REPO_NAME and not derived from the
    folder: in a container the code sits in /app and the signature would say
    "app". Here the tests run from the real repository, so the two names have to
    match — that is how a folder rename shows up."""
    f = F.signature()
    assert f["version"] == F.VERSION
    assert f["repo"] == F.REPO_NAME == F.REPO_ROOT.name
    # the commit is there because the app runs from a git repository; the day it
    # does not, the page still has to hold and the signature come back empty
    assert f["commit"] == "" or len(f["commit"]) == 7
    # The commit date is a real date or nothing: never one taken from somewhere
    # else (the ref's mtime) and nearly right.
    assert f["commit_date"] is None or isinstance(f["commit_date"], dt.date)


def test_the_commit_date_is_read_from_the_git_object(tmp_path):
    """The date comes out of the object in .git/objects, read by hand like the rest
    of the signature: no `git` subprocess."""
    import zlib

    sha = "1bdfcb2aa11223344556677889900aabbccddeef"  # 40 characters, like git
    body = (b"tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904\n"
             b"author G <g@x> 1755100800 +0200\n"
             b"committer G <g@x> 1755100800 +0200\n\n"
             b"Un commit\n")
    raw = b"commit " + str(len(body)).encode() + b"\0" + body
    folder = tmp_path / ".git" / "objects" / sha[:2]
    folder.mkdir(parents=True)
    (folder / sha[2:]).write_bytes(zlib.compress(raw))

    read_back = F._commit_date(tmp_path, sha)
    assert read_back == dt.datetime.fromtimestamp(1755100800).date()


def test_without_the_git_object_the_date_is_missing_not_invented(tmp_path):
    """After a `git gc` the object is inside a packfile: the page shows the sha
    alone. Better no date than the ref's mtime passed off as the commit date —
    after a clone or a reset it is not the same thing."""
    assert F._commit_date(tmp_path, "1bdfcb2aa11223344556677889900aabbccddeef") is None
    assert F._commit_date(tmp_path, "troppocorto") is None


def test_the_commit_is_read_from_packed_refs_too(tmp_path):
    """After a `git gc` the branch ref no longer has a file of its own."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
    (git / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        "1bdfcb2aa11223344556677889900aabbccddeef refs/heads/master\n",
        encoding="utf-8")

    # The sha comes back whole: it is the key that opens the object and reads
    # its date. Truncating it to seven is the signature's job — that is where how
    # a thing is shown gets decided.
    assert F._current_commit(tmp_path) == (
        "master", "1bdfcb2aa11223344556677889900aabbccddeef")
    assert F.signature()["commit"] == F._current_commit(F.REPO_ROOT)[1][:7]


def test_without_git_the_signature_still_holds(tmp_path):
    assert F._current_commit(tmp_path) == ("", "")


def test_a_document_that_is_not_utf8_is_refused_not_mangled(tmp_path):
    """The document is READ with `errors="replace"` so the page can show it.
    Writing that back would put U+FFFD on disk in place of every byte it could
    not decode — the whole file, not the header — and answer 200. A file saved
    by a Windows editor in cp1252 is not a laboratory case.
    """
    root = tmp_path / "projects"
    (root / "prog").mkdir(parents=True)
    p = root / "prog" / "CURRENT_STATUS.md"
    p.write_bytes("# Perché\n\n**Stato:** attivo\n\nNota: città, però.\n".encode("cp1252"))
    before = p.read_bytes()

    assert F.set_status("prog", str(root), "concluso") is None
    assert p.read_bytes() == before, "not one byte may change"


def test_the_line_endings_the_document_had_are_the_ones_it_keeps(tmp_path):
    """A one-line change must not come back as a whole-file diff. `read_text`
    and `write_text` translate every line ending between them, so a CRLF
    document written on Windows came back all LF."""
    root = tmp_path / "projects"
    (root / "prog").mkdir(parents=True)
    p = root / "prog" / "CURRENT_STATUS.md"
    p.write_bytes(b"# P\r\n\r\n**Status:** active\r\n**Next step:** x\r\n")

    F.set_status("prog", str(root), "done")

    raw = p.read_bytes()
    assert b"**Status:** done" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n"), "a lone LF appeared"


def test_the_header_in_a_code_block_is_not_the_header(tmp_path):
    """⚠️ Reachable from the page: a document that SHOWS the format in a fenced
    block before its own header had the EXAMPLE rewritten — the real header never
    changed, so the card kept showing the old status and every click damaged
    another line of the document."""
    root = tmp_path / "projects"
    (root / "prog").mkdir(parents=True)
    p = root / "prog" / "CURRENT_STATUS.md"
    p.write_text("# P\n\nHow the header goes:\n\n```markdown\n**Status:** active\n```\n\n"
                 "**Status:** waiting\n**Next step:** the real one\n", encoding="utf-8")

    F.set_status("prog", str(root), "done")

    text = p.read_text(encoding="utf-8")
    assert "```markdown\n**Status:** active" in text, "the example was rewritten"
    assert "\n**Status:** done" in text, "the real header was not"


def test_a_field_far_below_the_header_is_body_text(tmp_path):
    """The card offers no button for it — `read_project` only reads the head —
    so the route must not write there either."""
    root = tmp_path / "projects"
    (root / "prog").mkdir(parents=True)
    p = root / "prog" / "CURRENT_STATUS.md"
    p.write_text("# P\n\n**Status:** active\n\n" + "filler\n" * 45 +
                 "**Status:** waiting\n", encoding="utf-8")

    F.set_status("prog", str(root), "done")

    text = p.read_text(encoding="utf-8")
    assert text.index("**Status:** done") < text.index("filler")
    assert text.rstrip().endswith("**Status:** waiting"), "the body line was touched"


def test_a_document_that_is_a_symlink_stays_one(tmp_path):
    """`os.replace` replaced the LINK with a plain file: the real document was
    left behind still saying the old thing, and the project quietly forked in
    two. Somebody who linked their document somewhere meant it."""
    root = tmp_path / "projects"
    (root / "prog" / "docs").mkdir(parents=True)
    real = root / "prog" / "docs" / "status.md"
    real.write_text("# P\n\n**Status:** active\n", encoding="utf-8")
    link = root / "prog" / "CURRENT_STATUS.md"
    link.symlink_to(real)

    F.set_status("prog", str(root), "done")

    assert link.is_symlink(), "the link was replaced by a file"
    assert "**Status:** done" in real.read_text(encoding="utf-8")


def test_writing_preserves_owner_and_permissions(tmp_path, posix_permissions):
    """A new file inherits owner and permissions from whoever writes it, not from
    whoever was there before: in a container that is root, and after a "Close"
    the status document was left as root:root, no longer editable by its author.
    These tests do not run as root, so they check what can be checked: the
    permissions stay as they were, and the owner does not change."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    p.chmod(0o640)
    before = p.stat()

    F.set_status("prog", str(root), "concluso")
    after = p.stat()

    assert stat.S_IMODE(after.st_mode) == 0o640
    assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)


# ---- two roots and the tags ----------------------------------------------------

def _personal_root(folder):
    return a_root(folder, host="/host/home", key="personale",
               tags=("personal",), prefix="~/")


def test_a_roots_tags_apply_to_all_its_projects(tmp_path):
    """No backfill: where a project sits is a fact, deriving a tag from it is not
    inventing one. The document is only there to add what the position does not
    know."""
    write(tmp_path / "lavoro", "CURRENT_STATUS.md",
           "# L\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n")

    assert F.read_project(tmp_path / "lavoro", a_root()).tags == ("work",)


def test_the_document_adds_its_tags_to_the_roots(tmp_path):
    """The case one exclusive domain could not express: "in production" is true of
    THIS project, not of the folder holding it."""
    write(tmp_path / "api", "CURRENT_STATUS.md",
           "# A\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n"
           "**Tags:** prod, client-acme\n")

    assert F.read_project(tmp_path / "api", a_root()).tags == ("work", "prod", "client-acme")


def test_a_minus_removes_an_inherited_tag(tmp_path):
    """The personal project sitting among the work ones: without a way of removing
    the root's tag, inheritance would be a cage."""
    write(tmp_path / "sito", "CURRENT_STATUS.md",
           "# S\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n"
           "**Tags:** -work, personal\n")

    assert F.read_project(tmp_path / "sito", a_root()).tags == ("personal",)


def test_the_prod_field_becomes_a_tag_and_stays_a_note(tmp_path):
    """`Prod` has a field of its own because its value says WHERE it runs: that
    goes into the badge's note, and the tag is what filters."""
    write(tmp_path / "api", "CURRENT_STATUS.md",
           "# A\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n"
           "**Prod:** api-gateway\n")
    f = F.read_project(tmp_path / "api", a_root())

    assert f.tags == ("work", "prod")
    assert f.in_production is True and f.prod_note == "api-gateway"


@pytest.mark.parametrize("line,expected", [
    ("**Tags:** prod", ("work", "prod")),
    ("**Tag:** Prod", ("work", "prod")),                    # maiuscole: stesso tag
    ("**Tags:** prod, prod", ("work", "prod")),             # repeated: only one
    ("**Etichette:** in produzione", ("work", "in-produzione")),
    ("**Labels:** client_acme", ("work", "client-acme")),
    ("**Domain:** personal", ("work", "personal")),         # the old field name is still read
    ("**Dominio:** privato", ("work", "personal")),         # e i suoi valori storici pure
    ("**Tags:**", ("work",)),                               # empty: the root's own are what is left
    ("**Tags:** ---", ("work",)),                           # nothing usable: same
])
def test_tag_aliases_and_normalisation(tmp_path, line, expected):
    d = tmp_path / ("p_" + str(abs(hash(line))))
    write(d, "CURRENT_STATUS.md",
           f"# P\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n{line}\n")

    assert F.read_project(d, a_root()).tags == expected


def test_tags_are_counted_by_frequency(tmp_path):
    """The order is the one the page shows the filters in: the ones that really
    describe the set come first."""
    for name, line in [("a", "**Tags:** prod"), ("b", "**Tags:** prod"), ("c", "")]:
        write(tmp_path / name, "CURRENT_STATUS.md",
               f"# {name}\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-10\n{line}\n")

    projects = F.scan([a_root(tmp_path)], "")

    assert F.count_tags(projects) == [("work", 3), ("prod", 2)]


def test_scanning_two_roots(tmp_path):
    lavoro, casa = tmp_path / "projects", tmp_path / "home"
    write(lavoro / "erp", "CURRENT_STATUS.md",
           "# E\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-12\n")
    write(casa / "notes", "CURRENT_STATUS.md",
           "# U\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-11\n")

    projects = F.scan([a_root(lavoro, host="/h/p"), _personal_root(casa)],
                         str(tmp_path / "no.md"))
    by_name = {f.name: f for f in projects}

    assert set(by_name) == {"erp", "notes"}
    assert by_name["erp"].tags == ("work",)
    assert by_name["notes"].tags == ("personal",)
    assert by_name["notes"].root == "personale"
    assert by_name["notes"].prefix == "~/"
    assert by_name["notes"].status_file == "/host/home/notes/CURRENT_STATUS.md"


def test_two_folders_with_the_same_name_are_two_projects(tmp_path):
    """The name alone no longer identifies a project: the root is part of its
    address. Without that, the silence line would lead to the wrong card and
    "Close" would write into another project's file."""
    lavoro, casa = tmp_path / "projects", tmp_path / "home"
    write(lavoro / "notes", "CURRENT_STATUS.md",
           "# lavoro\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-12\n")
    write(casa / "notes", "CURRENT_STATUS.md",
           "# casa\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-11\n")

    projects = F.scan([a_root(lavoro), _personal_root(casa)], str(tmp_path / "no.md"))

    assert len(projects) == 2
    identi = {f.ident for f in projects}
    assert identi == {"projects:notes", "personale:notes"}
    # and the write stays inside the root it was handed
    F.set_status("notes", str(casa), "concluso", today=dt.date(2026, 8, 13))
    assert F.read_project(lavoro / "notes", a_root()).status == F.ACTIVE
    assert F.read_project(casa / "notes", a_root()).status == F.DONE


def test_a_root_that_does_not_exist_does_not_break(tmp_path):
    lavoro = tmp_path / "projects"
    write(lavoro / "erp", "CURRENT_STATUS.md",
           "# E\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-12\n")

    projects = F.scan([a_root(lavoro), _personal_root(tmp_path / "mai_esistita")],
                         str(tmp_path / "no.md"))
    assert [f.name for f in projects] == ["erp"]


def test_a_root_inside_another_does_not_produce_duplicates(tmp_path):
    """One root can sit inside another: the folder of a root is not a project of
    the other one, or it would show up twice under two different addresses."""
    casa = tmp_path / "home"
    lavoro = casa / "projects"
    write(lavoro / "erp", "CURRENT_STATUS.md",
           "# E\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-12\n")
    # the projects root has a CURRENT_STATUS.md of its own: it is not a project
    write(lavoro, "CURRENT_STATUS.md", "# indice\n\n**Stato:** attivo\n")
    write(casa / "notes", "CURRENT_STATUS.md",
           "# U\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-11\n")

    projects = F.scan([a_root(lavoro), _personal_root(casa)], str(tmp_path / "no.md"))
    assert sorted(f.name for f in projects) == ["erp", "notes"]


def test_index_only_projects_belong_to_the_first_root(tmp_path):
    """MEMORY.md parla di `~/projects` e basta."""
    lavoro, casa = tmp_path / "projects", tmp_path / "home"
    lavoro.mkdir(parents=True)
    casa.mkdir(parents=True)
    mem = tmp_path / "MEMORY.md"
    mem.write_text("## Progetti\n\n- **attivo** — [Tracker](t.md) — `~/projects/tracker/` roba\n",
                   encoding="utf-8")

    projects = F.scan([a_root(lavoro), _personal_root(casa)], str(mem))

    assert len(projects) == 1
    assert projects[0].root == "projects" and projects[0].tags == ("work",)
    assert projects[0].ident == "projects:tracker"


def test_the_tags_of_two_roots_are_counted_separately(tmp_path):
    lavoro, casa = tmp_path / "projects", tmp_path / "home"
    write(lavoro / "erp", "CURRENT_STATUS.md", "# E\n\n**Stato:** attivo\n")
    solo_lavoro = F.scan([a_root(lavoro)], str(tmp_path / "no.md"))

    assert F.count_tags(solo_lavoro) == [("work", 1)]

    write(casa / "notes", "CURRENT_STATUS.md", "# U\n\n**Stato:** attivo\n")
    tutti = F.scan([a_root(lavoro), _personal_root(casa)], str(tmp_path / "no.md"))
    # On equal frequency the order is alphabetical, so two readings of the
    # same page do not show the filters in a different order.
    assert F.count_tags(tutti) == [("personal", 1), ("work", 1)]


# ---- the fingerprint: the page reloads only if something changed ---------

def test_the_fingerprint_is_stable_when_nothing_changes(tmp_path):
    root = tmp_path / "projects"
    write(root / "p", "CURRENT_STATUS.md", ORIGINALE)
    mem = tmp_path / "no.md"

    before = F.fingerprint([a_root(root)], str(mem))
    assert before == F.fingerprint([a_root(root)], str(mem))


def test_the_fingerprint_changes_when_a_file_changes(tmp_path):
    root = tmp_path / "projects"
    p = write(root / "p", "CURRENT_STATUS.md", ORIGINALE)
    mem = tmp_path / "no.md"
    before = F.fingerprint([a_root(root)], str(mem))

    p.write_text(ORIGINALE.replace("attivo", "sospeso"), encoding="utf-8")
    assert F.fingerprint([a_root(root)], str(mem)) != before


def test_the_fingerprint_changes_when_a_project_appears_or_goes(tmp_path):
    root = tmp_path / "projects"
    write(root / "p", "CURRENT_STATUS.md", ORIGINALE)
    mem = tmp_path / "no.md"
    before = F.fingerprint([a_root(root)], str(mem))

    write(root / "new_status", "CURRENT_STATUS.md", ORIGINALE)
    after = F.fingerprint([a_root(root)], str(mem))
    assert after != before

    (root / "new_status" / "CURRENT_STATUS.md").unlink()
    assert F.fingerprint([a_root(root)], str(mem)) == before


def test_the_fingerprint_watches_the_index_too(tmp_path):
    root = tmp_path / "projects"
    root.mkdir(parents=True)
    mem = tmp_path / "MEMORY.md"
    mem.write_text("## Progetti\n", encoding="utf-8")
    before = F.fingerprint([a_root(root)], str(mem))

    mem.write_text("## Progetti\n\n- **attivo** — [T](t.md) — `~/projects/t/`\n",
                   encoding="utf-8")
    assert F.fingerprint([a_root(root)], str(mem)) != before


def test_the_fingerprint_covers_every_root(tmp_path):
    lavoro, casa = tmp_path / "projects", tmp_path / "home"
    write(lavoro / "erp", "CURRENT_STATUS.md", ORIGINALE)
    casa.mkdir(parents=True)
    roots = [a_root(lavoro), _personal_root(casa)]
    before = F.fingerprint(roots, str(tmp_path / "no.md"))

    write(casa / "notes", "CURRENT_STATUS.md", ORIGINALE)
    assert F.fingerprint(roots, str(tmp_path / "no.md")) != before


def test_no_status_line_no_button_to_show(tmp_path):
    """The "Close" button rewrites the status line: where that line is missing the
    write refuses — so the button must not even appear. This happened on
    documents carrying an `Updated` field but no `Status` one: the command was
    there and the only possible outcome was an error."""
    write(tmp_path / "meta", "CURRENT_STATUS.md",
           "# M\n\n**Aggiornato:** 2026-07-19\n**Radio**: RadioMaster Pocket\n")
    f = F.read_project(tmp_path / "meta", a_root())

    assert f.has_header is True          # there is a header
    assert f.has_status is False          # but not the line that decides
    assert f.status == F.UNDECLARED
    assert F.set_status("meta", str(tmp_path), "concluso") is None


def test_an_empty_status_line_stays_rewritable(tmp_path):
    """A status line with no value is still a line that can be rewritten: the
    question is whether the line is there, not whether the value is filled in."""
    write(tmp_path / "p", "CURRENT_STATUS.md", "# P\n\n**Stato:**\n**Aggiornato:** 2026-08-01\n")
    f = F.read_project(tmp_path / "p", a_root())

    assert f.has_status is True and f.status == F.UNDECLARED
    assert F.set_status("p", str(tmp_path), "concluso",
                           today=dt.date(2026, 8, 13))["status"] == F.DONE


# ---- creating a project -------------------------------------------------
# The second write of the app. The tests below ARE the perimeter: if one of
# them falls, the app can write where it must not.

def _a_root(tmp_path, key="projects"):
    d = tmp_path / key
    d.mkdir(exist_ok=True)
    return F.Root(key=key, folder=str(d), host=str(d),
                    tags=("work",), prefix="~/projects/")


DESC_OK = "Un progetto di prova che serve a verificare la creazione di un fronte new_status"


def test_create_writes_the_folder_and_the_header(tmp_path):
    r = _a_root(tmp_path)
    result = F.create_project("nuovo_progetto", r, DESC_OK, app_name="Nuovo Progetto")

    assert "error" not in result
    text = (tmp_path / "projects" / "nuovo_progetto" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Status:** active" in text         # the only honest value: the ball is ours
    assert f"**Updated:** {dt.date.today().isoformat()}" in text
    assert "**Next step:**\n" in text           # empty: it cannot be derived from facts
    assert "**Waiting for:**\n" in text
    assert f"**Description:** {DESC_OK}" in text
    assert "**App:** Nuovo Progetto" in text


def test_create_writes_in_the_configured_language(tmp_path):
    """A NEW document has no language to inherit: whoever runs Frontstep picks it.
    From then on the document is the one dictating it."""
    r = _a_root(tmp_path)
    F.create_project("progetto_it", r, DESC_OK, app_name="Progetto", language="it")

    text = (tmp_path / "projects" / "progetto_it" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Stato:** attivo" in text
    assert f"**Aggiornato:** {dt.date.today().isoformat()}" in text
    assert "**Prossimo passo:**\n" in text
    assert "**In attesa di:**\n" in text
    assert f"**Descrizione:** {DESC_OK}" in text
    # and the dashboard reads it back like any other
    assert F.read_project(tmp_path / "projects" / "progetto_it", a_root()).status == F.ACTIVE


def test_adopting_a_folder_does_not_touch_its_content(tmp_path):
    """An existing folder used to be refused outright. The invariant changed so
    that a project older than the dashboard could be adopted, and the defence is
    now more precise: ONLY the status document is added, and nothing else in the
    folder is created, rewritten or removed."""
    r = _a_root(tmp_path)
    d = tmp_path / "projects" / "occupato"
    d.mkdir()
    (d / "roba.txt").write_text("mia", encoding="utf-8")
    (d / "sotto").mkdir()

    before = sorted(x.name for x in d.iterdir())
    result = F.create_project("occupato", r, DESC_OK)

    assert result.get("adopted") is True
    assert (d / "roba.txt").read_text(encoding="utf-8") == "mia"
    assert sorted(x.name for x in d.iterdir()) == sorted(before + ["CURRENT_STATUS.md"])


@pytest.mark.parametrize("bad", [
    "../fuori", "..", "a/b", "a\\b", ".nascosto", "", " ", "x" * 65, "con spazio",
    "/assoluto", "..%2f", "-", "_",
])
def test_create_refuses_dangerous_names(tmp_path, bad):
    r = _a_root(tmp_path)
    assert "error" in F.create_project(bad, r, DESC_OK)
    # and above all: it created nothing, anywhere
    assert list((tmp_path / "projects").iterdir()) == []


def test_create_accepts_accented_names(tmp_path):
    """I nomi veri li contengono: `marginalitá_contract` esiste."""
    r = _a_root(tmp_path)
    assert "error" not in F.create_project("marginalitá_x", r, DESC_OK)
    assert (tmp_path / "projects" / "marginalitá_x").is_dir()


def test_create_refuses_a_symlink_pointing_out(tmp_path):
    """The check comes AFTER resolve(), so a link pointing outside the root falls
    too — not just a `../` in the string."""
    r = _a_root(tmp_path)
    fuori = tmp_path / "fuori"
    fuori.mkdir()
    (tmp_path / "projects" / "trappola").symlink_to(fuori, target_is_directory=True)

    assert "error" in F.create_project("trappola", r, DESC_OK)
    assert not (fuori / "CURRENT_STATUS.md").exists()


@pytest.mark.parametrize("description", ["", "   ", "x" * 141])
def test_create_refuses_an_empty_or_too_long_description(tmp_path, description):
    """A description is needed (without one the card is born mute) and no more than
    140 characters (past that it does not fit a card). There is no minimum: that
    was a style guideline, not a constraint of the format."""
    r = _a_root(tmp_path)
    assert "error" in F.create_project("progetto", r, description)
    assert list((tmp_path / "projects").iterdir()) == []


def test_create_accepts_a_short_description(tmp_path):
    """A brand new project does not always have much to say yet."""
    r = _a_root(tmp_path)
    assert "error" not in F.create_project("breve", r, "Prove di stampa 3D")
    text = (tmp_path / "projects" / "breve" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Description:** Prove di stampa 3D" in text


def test_create_normalises_line_breaks_in_the_description(tmp_path):
    """A line break inside the field would cut the description short at the parser."""
    r = _a_root(tmp_path)
    spezzata = DESC_OK.replace(" a ", "\n a ")
    assert "error" not in F.create_project("progetto", r, spezzata)
    text = (tmp_path / "projects" / "progetto" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    line = [r for r in text.split("\n") if r.startswith("**Description:**")][0]
    assert line == f"**Description:** {DESC_OK}"


def test_a_new_project_shows_up_in_the_next_scan(tmp_path):
    """Created and seen: the only proof that counts for whoever watches the page."""
    r = _a_root(tmp_path)
    F.create_project("appena_nato", r, DESC_OK, app_name="Appena Nato")

    projects = F.scan([r], str(tmp_path / "no.md"))
    trovato = [f for f in projects if f.name == "appena_nato"][0]
    assert trovato.status == F.ACTIVE
    assert trovato.description == DESC_OK
    assert trovato.app_name == "Appena Nato"
    assert trovato.updated == dt.date.today()


def test_the_description_accepts_emoji_the_name_does_not(tmp_path):
    """An emoji in the description is fine. In the folder name it is not — that
    stays letters, digits, dot, dash and underscore, because it is a path on
    disk."""
    r = _a_root(tmp_path)
    assert "error" not in F.create_project("stampa3d", r, "Prove di stampa 3D 🖨️")
    text = (tmp_path / "projects" / "stampa3d" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "🖨️" in text

    assert "error" in F.create_project("stampa🖨️", r, "Prove di stampa 3D")
    assert not (tmp_path / "projects" / "stampa🖨️").exists()


def test_create_adopts_a_folder_without_a_document(tmp_path):
    """Folder already there, document missing: the case of a project born before
    the dashboard, or moved in from elsewhere. The document is added and nothing
    else is touched."""
    r = _a_root(tmp_path)
    esistente = tmp_path / "projects" / "gia_mia"
    esistente.mkdir()
    (esistente / "codice.py").write_text("print('mio')", encoding="utf-8")

    result = F.create_project("gia_mia", r, "Un progetto che esisteva prima della dashboard")

    assert result.get("adopted") is True
    assert (esistente / "CURRENT_STATUS.md").is_file()
    assert (esistente / "codice.py").read_text(encoding="utf-8") == "print('mio')"


def test_create_does_not_overwrite_an_existing_document(tmp_path):
    """This is the real defence: not "the folder must not exist" but "the document
    is not touched". It holds for any casing of the file name."""
    r = _a_root(tmp_path)
    d = tmp_path / "projects" / "gia_fatta"
    write(d, "current_status.md", "# Mio\n\n**Stato:** attivo\n")

    assert "error" in F.create_project("gia_fatta", r, "Una description qualsiasi per il test")
    assert (d / "current_status.md").read_text(encoding="utf-8") == "# Mio\n\n**Stato:** attivo\n"


def test_create_does_not_leave_a_second_document_beside_the_one_there(
        tmp_path, case_sensitive_fs):
    """The other half of the test above, and it can only be asked where the two
    names are two files. On a case-insensitive filesystem — macOS by default,
    Windows, and a Linux box mounted that way — `current_status.md` and
    `CURRENT_STATUS.md` ARE the same file, so "no second document appeared" is
    not a property that can hold or fail there.

    Kept apart rather than dropped: what must never happen anywhere is the
    OVERWRITE, and that is asserted above, on every system.
    """
    r = _a_root(tmp_path)
    d = tmp_path / "projects" / "gia_fatta"
    write(d, "current_status.md", "# Mio\n\n**Stato:** attivo\n")

    F.create_project("gia_fatta", r, "Una description qualsiasi per il test")

    assert not (d / "CURRENT_STATUS.md").exists()


# ---- bilingual: documents already written do not change language -----------------
#
# This is what the single-codebase decision rests on: the Italian documents
# already written have to work without migrating one, and stay Italian
# even after the dashboard has written into them.

IT = """# Progetto

**Stato:** attivo
**Aggiornato:** 2026-08-10
**Prossimo passo:** Rileggere il piano
**In attesa di:** Robin
**App:** Cruscotto
**Descrizione:** Un progetto scritto in italiano
"""

EN = """# Project

**Status:** active
**Updated:** 2026-08-10
**Next step:** Re-read the plan
**Waiting for:** Robin
**App:** Dashboard
**Description:** A project written in English
"""


@pytest.mark.parametrize("text,language", [(IT, "it"), (EN, "en")])
def test_fields_are_read_in_both_languages(tmp_path, text, language):
    d = tmp_path / f"p_{language}"
    write(d, "CURRENT_STATUS.md", text)
    f = F.read_project(d, a_root(host="/host"))

    assert f.status == F.ACTIVE
    assert f.updated == dt.date(2026, 8, 10)
    assert f.waiting_for == "Robin"
    assert f.app_name in ("Cruscotto", "Dashboard")
    assert f.next_step.startswith(("Rileggere", "Re-read"))
    assert f.description.startswith(("Un progetto", "A project"))
    assert f.description_derived is False


@pytest.mark.parametrize("text,waiting_for", [(IT, "it"), (EN, "en")])
def test_the_documents_language_is_recognised(text, waiting_for):
    assert F.document_language(text.split("\n")) == waiting_for


def test_with_no_recognisable_field_english_wins():
    """The project's canonical language: with no clues, that is what gets written."""
    assert F.document_language("# Solo un title\n\ne del text".split("\n")) == "en"


def test_app_and_prod_do_not_vote_on_the_language():
    """They are spelled the same in both languages: they say nothing, and letting
    them vote would give a random language to a document that has only those."""
    lines = "# P\n\n**App:** X\n**Prod:** container\n".split("\n")
    assert F.document_language(lines) == "en"


def test_closing_an_italian_document_leaves_it_italian(tmp_path):
    """⚠️ The test the single codebase rests on: the dashboard is only passing
    through, but the document belongs to whoever wrote it and must not change
    language under their hands for the sake of one keypress."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", IT)

    result = F.set_status("prog", str(root), F.DONE, today=dt.date(2026, 8, 14))
    after = p.read_text(encoding="utf-8")

    assert "**Stato:** concluso" in after
    assert "**Aggiornato:** 2026-08-14" in after
    assert "**Status:**" not in after and "**Updated:**" not in after
    # but what comes back to the page is the canonical one: the page speaks one language
    assert result["status"] == F.DONE
    assert F.read_project(root / "prog", a_root()).status == F.DONE


def test_closing_an_english_document_leaves_it_english(tmp_path):
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", EN)

    F.set_status("prog", str(root), F.PAUSED, today=dt.date(2026, 8, 14))
    after = p.read_text(encoding="utf-8")

    assert "**Status:** paused" in after
    assert "**Updated:** 2026-08-14" in after
    assert "**Stato:**" not in after


def test_the_field_name_the_document_uses_is_kept(tmp_path):
    """A tolerated alias stays as it is: whoever wrote `Last updated` does not see
    it turn into `Updated` for pressing a key."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md",
               "# P\n\n**Status:** active\n**Last updated:** 2026-08-01\n")

    F.set_status("prog", str(root), F.DONE, today=dt.date(2026, 8, 14))
    after = p.read_text(encoding="utf-8")

    assert "**Last updated:** 2026-08-14" in after
    assert "**Updated:**" not in after


def test_a_mixed_header_breaks_nothing(tmp_path):
    """It happens to anyone translating half way: it is read all the same, and on
    writing the language with more fields wins."""
    d = tmp_path / "p"
    write(d, "CURRENT_STATUS.md",
           "# P\n\n**Status:** attivo\n**Aggiornato:** 2026-08-10\n"
           "**Prossimo passo:** finire di tradurre\n")
    f = F.read_project(d, a_root(host="/host"))

    assert f.status == F.ACTIVE                       # an Italian value under an English field name
    assert f.next_step == "finire di tradurre"
    assert F.document_language(
        (d / "CURRENT_STATUS.md").read_text(encoding="utf-8").split("\n")) == "it"


def test_the_old_domain_values_map_onto_tags(tmp_path):
    """`Domain` was an enum of two entries, not a free tag: `PERSONALE` and
    `personal` were the same domain. Measured on real documents: without this
    mapping, `personal` (7 projects) and `personale` (1) showed up as two
    different filters."""
    write(tmp_path / "sito", "CURRENT_STATUS.md",
           "# S\n\n**Stato:** attivo\n**Domain:** PERSONALE\n")

    assert F.read_project(tmp_path / "sito", a_root()).tags == ("work", "personal")


def test_the_same_value_written_as_a_tag_stays_as_is(tmp_path):
    """Whoever writes `Tags: personale` means that tag: the aliases apply only to
    the historical names of the field, not to what someone declares today."""
    write(tmp_path / "sito", "CURRENT_STATUS.md",
           "# S\n\n**Stato:** attivo\n**Tags:** personale\n")

    assert F.read_project(tmp_path / "sito", a_root()).tags == ("work", "personale")


# ---- the third write: the next step, from the card -------------------
#
# It shares its whole implementation with "Close" (`_apply_to_header`), so what
# is tested here is what is DIFFERENT: which line moves, what happens when the
# line is not there, and that free text cannot leave the field it belongs to.

def test_writing_the_next_step_moves_the_date_too(tmp_path):
    """In the end-of-session ritual they are one gesture: a next step declared
    under last month's date claims the work moved when it did not."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    result = F.set_next_step("prog", str(root), "Chiudere il §5",
                            today=dt.date(2026, 8, 14))
    after = p.read_text(encoding="utf-8")

    assert result == {"name": "prog", "next_step": "Chiudere il §5",
                     "updated": "2026-08-14"}
    assert "**Prossimo passo:** Chiudere il §5" in after
    assert "**Aggiornato:** 2026-08-14" in after


def test_only_the_next_step_and_the_date_are_rewritten(tmp_path):
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    F.set_next_step("prog", str(root), "Altro", today=dt.date(2026, 8, 14))
    before = ORIGINALE.split("\n")
    after = p.read_text(encoding="utf-8").split("\n")

    assert len(before) == len(after)
    assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [3, 4]
    # the status is not touched: writing the next step is not reopening anything
    assert "**Stato:** attivo" in "\n".join(after)


def test_with_no_next_step_line_nothing_is_written(tmp_path):
    """Same rule as Close: a header without that line does not get one invented
    for it, and the page does not show the command either (`has_next_step`)."""
    root = tmp_path / "projects"
    without = "# P\n\n**Stato:** attivo\n**Aggiornato:** 2026-01-05\n"
    p = write(root / "prog", "CURRENT_STATUS.md", without)

    assert F.set_next_step("prog", str(root), "qualcosa") is None
    assert p.read_text(encoding="utf-8") == without


def test_an_empty_next_step_line_is_writable(tmp_path):
    """The most common case there is: a project waiting for its next step."""
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md",
           "# P\n\n**Stato:** attivo\n**Prossimo passo:**\n")

    assert F.read_project(root / "prog", a_root()).has_next_step is True
    assert F.set_next_step("prog", str(root), "Rileggere il piano") is not None
    assert F.read_project(root / "prog", a_root()).next_step == "Rileggere il piano"


def test_no_next_step_line_no_command_to_show(tmp_path):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", "# P\n\n**Stato:** attivo\n")

    assert F.read_project(root / "prog", a_root()).has_next_step is False


def test_the_next_step_can_be_emptied(tmp_path):
    """Clearing it is a legitimate act: the ball moved and there is nothing
    declared for the next session yet."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    F.set_next_step("prog", str(root), "")
    assert "**Prossimo passo:**\n" in p.read_text(encoding="utf-8")
    assert F.read_project(root / "prog", a_root()).next_step == ""


def test_line_breaks_in_the_next_step_are_folded(tmp_path):
    """The parser reads the field with a single-line regex: a break inside the
    value would cut it short, and the rest would become a line of the body."""
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    F.set_next_step("prog", str(root), "Prima riga\nseconda   riga\n")

    assert F.read_project(root / "prog", a_root()).next_step == "Prima riga seconda riga"


def test_the_next_step_has_no_length_cap(tmp_path):
    """A maximum here would be a style guideline dressed up as a constraint: the
    convention asks for one imperative line, and asking is what it does."""
    root = tmp_path / "projects"
    long_text = "Rileggere il piano " * 30
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)

    assert F.set_next_step("prog", str(root), long_text) is not None
    assert F.read_project(root / "prog", a_root()).next_step == long_text.strip()


def test_writing_the_next_step_keeps_the_documents_language(tmp_path):
    """An English document keeps `**Next step:**`, an Italian one keeps
    `**Prossimo passo:**`: the file belongs to whoever wrote it."""
    root = tmp_path / "projects"
    inglese = ("# P\n\n**Status:** active\n**Updated:** 2026-01-05\n"
               "**Next step:** read the plan\n")
    p = write(root / "prog", "CURRENT_STATUS.md", inglese)

    F.set_next_step("prog", str(root), "ship it", today=dt.date(2026, 8, 14))
    after = p.read_text(encoding="utf-8")

    assert "**Next step:** ship it" in after
    assert "**Updated:** 2026-08-14" in after
    assert "Prossimo passo" not in after


def test_the_next_step_field_name_the_document_uses_is_kept(tmp_path):
    """`Next:` is an accepted alias: whoever wrote it does not find it renamed."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md",
               "# P\n\n**Status:** active\n**Next:** read the plan\n")

    F.set_next_step("prog", str(root), "ship it")

    assert "**Next:** ship it" in p.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["..", "../altro", "/etc", ""])
def test_the_next_step_is_never_written_outside_the_root(tmp_path, name):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    fuori = write(tmp_path / "altro", "CURRENT_STATUS.md", ORIGINALE)

    assert F.set_next_step(name, str(root), "qualcosa") is None
    assert fuori.read_text(encoding="utf-8") == ORIGINALE


def test_the_next_step_write_leaves_no_temporary_file(tmp_path):
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    F.set_next_step("prog", str(root), "Altro")

    assert [p.name for p in (root / "prog").iterdir()] == ["CURRENT_STATUS.md"]


def test_the_next_step_write_preserves_owner_and_permissions(tmp_path, posix_permissions):
    """Same defence as Close, and it has to hold for every write: in a container
    the process is root, and a document left root:root is no longer editable by
    the person who wrote it."""
    root = tmp_path / "projects"
    p = write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    p.chmod(0o640)

    F.set_next_step("prog", str(root), "Altro")

    assert stat.S_IMODE(p.stat().st_mode) == 0o640


def test_a_markdown_next_step_survives_the_round_trip(tmp_path):
    """What the page shows has been through the markdown filter; what gets
    written back is the raw line. Backticks and asterisks must come out the
    other side unchanged."""
    root = tmp_path / "projects"
    write(root / "prog", "CURRENT_STATUS.md", ORIGINALE)
    line = "Chiudere il **§4** e rileggere `core.py`"

    F.set_next_step("prog", str(root), line)

    assert F.read_project(root / "prog", a_root()).next_step == line


# ---- the tag colours: the hash alone is not enough ----------------------------

def test_the_two_commonest_tags_do_not_share_a_colour():
    """Measured, not assumed: `work`, `prod` and `client` all hash onto colour 6.
    With seven colours and a handful of tags a collision is the normal case, and
    on the band — the card's only strong colour channel — a collision is the
    whole distinction gone.

    It used to be `work`, `personal` and `finance` on colour 7. Dropping the red
    took the palette to seven and re-dealt every hash: the collision did not go
    away, it moved — onto the pair that describes a project at work that is in
    production, which is if anything a more common one."""
    assert F.color_index("work") == F.color_index("prod")   # the defect

    colors = F.assign_colors(["work", "prod", "client"])

    assert len(set(colors.values())) == 3


def test_the_most_used_tag_keeps_the_colour_its_name_asks_for():
    """Frequency order is the tie-break: the tag describing forty projects keeps
    its colour, the one describing two moves."""
    colors = F.assign_colors(["work", "prod"])

    assert colors["work"] == F.color_index("work")
    assert colors["prod"] != F.color_index("prod")


def test_assigning_colours_is_deterministic():
    """Same tags in the same order, same colours — on every reload and every
    machine. What is given up is only that a tag's colour depends on the set."""
    tags = ["work", "prod", "personal", "infra", "finance"]

    assert F.assign_colors(tags) == F.assign_colors(tags)


def test_more_tags_than_colours_does_not_break():
    """Past `TAG_COLORS`, every colour is taken and two tags looking alike is
    arithmetic. What must not happen is an exception or an index out of range."""
    tags = [f"tag-{i}" for i in range(20)]

    colors = F.assign_colors(tags)

    assert len(colors) == 20
    assert all(0 <= c < F.TAG_COLORS for c in colors.values())
    # the first ones are all different: nobody shares until they have to
    assert len(set(list(colors.values())[:F.TAG_COLORS])) == F.TAG_COLORS


def test_a_repeated_tag_keeps_one_colour():
    colors = F.assign_colors(["work", "work", "prod"])

    assert len(colors) == 2


def test_an_agents_file_that_is_not_utf8_does_not_take_the_project_down(tmp_path):
    """⚠️ `UnicodeDecodeError` is a ValueError, not an OSError, so it went
    straight through the `except` written to report exactly this: the route
    answered 500 with the project already created on disk.

    The project is made, and the failure is reported next to it."""
    r = _a_root(tmp_path)
    (tmp_path / "projects" / "esistente").mkdir(parents=True)
    (tmp_path / "projects" / "esistente" / "AGENTS.md").write_bytes(
        "# Già scritto, in cp1252\n".encode("cp1252"))

    result = F.create_project("esistente", r, "Una descrizione qualsiasi per il test",
                              with_agents=True)

    assert "error" not in result
    assert (tmp_path / "projects" / "esistente" / "CURRENT_STATUS.md").is_file()
    assert "agents_error" in result and "agents" not in result
