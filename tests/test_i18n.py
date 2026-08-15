"""The interface in two languages, and the traps that come with it.

Frontstep read and wrote documents in two languages from the start and spoke
only English around them. Choosing Italian during setup changed the documents
and left every button in English, which reads as a bug because it is one.

Most of what is here does not check a translation — a wrong word is a wrong
word and no test finds it. It checks the MECHANISM: that no key is orphaned,
that the client and the server share one catalogue, and that the loop variable
`t` never shadows the function `t` again.
"""
import datetime as dt
import json
import re
from pathlib import Path

import pytest

from frontstep import config as C, core as F, i18n as T, launch as L
from frontstep.web import create_app

TEMPLATES = Path(F.PACKAGE_DIR) / "templates"
STATIC = Path(F.PACKAGE_DIR) / "static"
MARKUP = "\n".join(p.read_text(encoding="utf-8") for p in sorted(TEMPLATES.glob("*.html")))
SCRIPTS = "\n".join((STATIC / n).read_text(encoding="utf-8")
                    for n in ("frontstep.js", "setup.js"))


def _app(tmp_path, language="en"):
    # A folder per language: two apps in one test would otherwise try to create
    # the same fixture twice.
    root = tmp_path / f"code-{language}"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "CURRENT_STATUS.md").write_text(
        "# Alpha\n\n**Status:** active\n**Updated:** 2026-08-01\n"
        "**Next step:** Read §4 again\n**Waiting for:**\n"
        "**Description:** A project used to check the interface\n", encoding="utf-8")
    cfg = C.Config(roots=[F.Root(key="code", folder=str(root), host=str(root),
                                 prefix="~/code/", label="Code", tags=("work",))],
                   language=language)
    return create_app(cfg).test_client()


# ---- the mechanism ---------------------------------------------------------

def test_every_key_the_templates_ask_for_exists():
    """A key with no translation degrades to English, which is the right
    failure — but silently, and a page half in each language looks like a bug
    nobody can name. This is what turns it into a red test instead."""
    asked = set(re.findall(r'\bt\(\s*"([^"]+)"\s*\)', MARKUP))
    # `plural(n, "day", "days")` asks for both forms at once.
    asked |= {k for pair in re.findall(r'\bplural\([^,]+,\s*"([^"]+)",\s*"([^"]+)"\)',
                                       MARKUP) for k in pair}

    assert sorted(k for k in asked if k not in T.IT) == []


def test_every_key_the_scripts_ask_for_exists():
    """Same for the strings written after a click. They come from the same
    catalogue precisely so one sentence cannot end up with two translations."""
    asked = set(re.findall(r'(?<![A-Za-z0-9_.])t\("([^"]+)"\)', SCRIPTS))

    assert sorted(k for k in asked if k not in T.IT) == []


def test_no_translation_is_left_orphaned():
    """The other direction: a key nobody asks for is a sentence that was
    reworded in English and left translated here — dead weight that reads as
    coverage."""
    asked = set(re.findall(r'\bt\(\s*"([^"]+)"\s*\)', MARKUP))
    # `plural(n, "day", "days")` asks for both forms at once.
    asked |= {k for pair in re.findall(r'\bplural\([^,]+,\s*"([^"]+)",\s*"([^"]+)"\)',
                                       MARKUP) for k in pair}
    asked |= set(re.findall(r'(?<![A-Za-z0-9_.])t\("([^"]+)"\)', SCRIPTS))
    # The section labels come from `core.SECTIONS` through `t(label)`, the
    # statuses through `LABELS`, and what a button will open through
    # `launch.DESCRIBED_NAMES` — all asked for by variable, not literal.
    asked |= {label for _, label, _ in F.SECTIONS} | set(F.LABELS.values())
    asked |= set(L.DESCRIBED_NAMES)

    # A key may carry a context prefix — `card|Paused`. What is asked for is the
    # text after it: the prefix only picks between two Italian words for one
    # English one, so it cannot make a translation orphaned on its own.
    assert sorted(k for k in T.IT if k.split("|", 1)[-1] not in asked) == []


def test_a_loop_variable_never_shadows_the_translation_function():
    """`{% for t in … %}` makes `t` a string for the whole block, and the next
    person to add a label inside gets "str is not callable" at a line that looks
    innocent. It has happened twice in this template set."""
    assert re.search(r"\{%\s*for\s+t\s+in\s", MARKUP) is None


def test_an_unknown_language_falls_back_instead_of_failing():
    """A working page in the project's own language beats an error about a
    language code."""
    assert T.t("Reload", "de") == "Reload"
    assert T.resolve("de", "it") == "it"
    assert T.resolve(None, "klingon") == "en"


def test_the_url_wins_over_the_configuration():
    """Like the staleness threshold: switching is a navigation, so a view stays
    shareable and survives a refresh without writing a file."""
    assert T.resolve("en", "it") == "en"
    assert T.resolve(None, "it") == "it"


# ---- what actually comes out of the page -----------------------------------

def test_the_page_comes_out_in_the_configured_language(tmp_path):
    page = _app(tmp_path, "it").get("/").get_data(as_text=True)

    assert "Nuovo progetto" in page
    assert "Linea del silenzio" in page
    assert 'html lang="it"' in page


def test_the_switcher_can_change_it_without_touching_the_configuration(tmp_path):
    client = _app(tmp_path, "it")

    english = client.get("/?lang=en").get_data(as_text=True)

    assert "New project" in english and "Nuovo progetto" not in english
    # and the configuration is untouched: the next plain request is Italian again
    assert "Nuovo progetto" in client.get("/").get_data(as_text=True)


def test_the_switcher_is_on_the_page_and_marks_the_current_one(tmp_path):
    page = _app(tmp_path, "it").get("/?lang=it").get_data(as_text=True)

    assert 'class="segmented seg-lang"' in page
    assert 'href="?lang=en' in page
    assert re.search(r'\?lang=it[^>]*aria-current="true"', page)


def test_the_scripts_are_handed_the_catalogue(tmp_path):
    """They write into innerHTML after a click, so their strings cannot be
    rendered by the server. Empty in English, where the key IS the text."""
    italian = _app(tmp_path, "it").get("/").get_data(as_text=True)
    english = _app(tmp_path, "en").get("/").get_data(as_text=True)

    block = re.search(r'<script type="application/json" id="i18n">(.*?)</script>',
                      italian, re.S).group(1)
    assert json.loads(block)["Writing"] == "Scrivo"
    assert re.search(r'id="i18n">\{\}</script>', english)


def test_the_setup_page_is_translated_too(tmp_path):
    """It is the first page anybody sees, and the one that ASKS for a language."""
    app = create_app(None)
    client = app.test_client()

    page = client.get("/", query_string={"key": app.config["FRONTSTEP_TOKEN"],
                                         "lang": "it"}).get_data(as_text=True)

    assert "Dove stanno i tuoi progetti" in page
    assert "Comincia" in page


def test_the_status_a_screen_reader_hears_is_translated(tmp_path):
    """The card says its status with the colour of its paper, so that one line
    is the whole of it for anybody not seeing colour — and it used to be the
    canonical value, `active`, announced in the middle of an Italian page.

    The paused one is here on purpose: `Paused` is the section title too, where
    Italian wants the plural, and rendering that word on a single card is how
    the two would quietly become one."""
    root = tmp_path / "code"
    for name, status in (("alpha", "active"), ("beta", "paused")):
        (root / name).mkdir(parents=True)
        (root / name / "CURRENT_STATUS.md").write_text(
            f"# {name}\n\n**Status:** {status}\n**Updated:** 2026-08-01\n",
            encoding="utf-8")
    cfg = C.Config(roots=[F.Root(key="code", folder=str(root), host=str(root),
                                 prefix="~/", label="C", tags=())], language="it")
    client = create_app(cfg).test_client()

    italian = client.get("/?lang=it").get_data(as_text=True)
    english = client.get("/?lang=en").get_data(as_text=True)

    assert '<span class="sr-only">Attivo,</span>' in italian
    assert '<span class="sr-only">Sospeso,</span>' in italian
    assert "Sospesi" in italian          # the section title keeps the plural
    assert '<span class="sr-only">Active,</span>' in english
    assert '<span class="sr-only">Paused,</span>' in english


def test_no_sentence_the_script_writes_skips_the_catalogue():
    """A string assigned straight into a title or into innerHTML never passed
    through `t()`, and it shows in one language only. The tooltip on Close and
    Pause was built that way — "Writes status done in the header of …" —
    English in the middle of an Italian page, with the canonical status in it."""
    written = re.findall(r'\.(?:title|textContent|innerHTML|placeholder)\s*=\s*"([A-Z][^"]+)"',
                         SCRIPTS)

    assert written == []


def test_only_the_names_that_describe_something_are_translated(tmp_path):
    """`the default Windows terminal` is a sentence about what will open, so it
    is interface. `Terminal` is macOS's application, and `kitty` is somebody's
    program: those are names, and a name is the same word in every language —
    running them through the catalogue would rename the user's terminal, since
    the label of the button happens to be that same English word."""
    root = tmp_path / "code"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "CURRENT_STATUS.md").write_text(
        "# Alpha\n\n**Status:** active\n**Updated:** 2026-08-01\n", encoding="utf-8")
    cfg = C.Config(roots=[F.Root(key="code", folder=str(root), host=str(root),
                                 prefix="~/", label="C", tags=())],
                   language="it", terminal=("Terminal", "{}"))
    page = create_app(cfg).test_client().get("/").get_data(as_text=True)

    assert "(Terminal)" in page                 # the program keeps its name
    assert "(Terminale)" not in page


def test_the_sentence_around_a_name_survives_it_being_translated():
    """Translating the name changed what follows the preposition, and Italian
    contracts a preposition with the article of the word after it. Measured in
    the page: "Apri la cartella IN IL programma con cui Windows apre i .md"."""
    wrong = (" in il ", " in lo ", " in la ", " in l'", " in i ", " in gli ")

    # The one place a name follows a preposition directly. On the terminal
    # button the name is in brackets after the path, so nothing agrees with it.
    for name in L.DESCRIBED_NAMES:
        phrase = f'{T.t("Open the folder with", "it")} {T.t(name, "it")}'

        assert not any(bad in phrase for bad in wrong), phrase


def test_one_day_is_not_one_days(tmp_path):
    """The axis of the silence line said "1 giorni fa", which is what a page
    says when a number and a word are put next to each other by hand."""
    root = tmp_path / "code"
    (root / "alpha").mkdir(parents=True)
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    (root / "alpha" / "CURRENT_STATUS.md").write_text(
        f"# Alpha\n\n**Status:** active\n**Updated:** {yesterday}\n", encoding="utf-8")
    cfg = C.Config(roots=[F.Root(key="code", folder=str(root), host=str(root),
                                 prefix="~/", label="C", tags=())], language="it")
    client = create_app(cfg).test_client()

    italian = client.get("/?lang=it").get_data(as_text=True)
    english = client.get("/?lang=en").get_data(as_text=True)

    assert "1 giorno fa" in italian and "1 giorni" not in italian
    assert "in silenzio da 1 giorno" in italian
    assert "1 day ago" in english and "1 days" not in english


def test_switching_language_never_moves_a_colour(tmp_path):
    """A tag's colour has to survive the switcher. It does, and for a reason
    worth keeping: the colour comes from the tag WRITTEN IN THE DOCUMENT, and
    the switcher does not touch documents — so there is nothing for it to move.

    The filters are here for the same reason: colours are assigned over every
    tag on the machine, not over the ones currently shown, so hiding a project
    cannot re-deal the others."""
    root = tmp_path / "code"
    for name, tags in (("alpha", "lavoro, prod"), ("beta", "personale"),
                       ("gamma", "lavoro, esempio")):
        (root / name).mkdir(parents=True)
        (root / name / "CURRENT_STATUS.md").write_text(
            f"# {name}\n\n**Stato:** attivo\n**Aggiornato:** 2026-08-01\n"
            f"**Tag:** {tags}\n", encoding="utf-8")
    cfg = C.Config(roots=[F.Root(key="code", folder=str(root), host=str(root),
                                 prefix="~/", label="C", tags=())], language="it")
    client = create_app(cfg).test_client()
    pattern = re.compile(r'data-tag="([^"]+)"\s+data-color="(\d+)"')

    def colours(url):
        return dict(sorted(set(pattern.findall(client.get(url).get_data(as_text=True)))))

    italian = colours("/?lang=it")

    assert italian, "the fixture has to produce coloured tags for this to mean anything"
    assert colours("/?lang=en") == italian
    assert colours("/?lang=en&stale_days=30") == italian


def test_a_document_keeps_its_own_language_whatever_the_page_is_in(tmp_path):
    """The interface is a preference; a file's language is a fact about that
    file. Reading the page in English must not rewrite an Italian header."""
    root = tmp_path / "code"
    (root / "prog").mkdir(parents=True)
    doc = root / "prog" / "CURRENT_STATUS.md"
    doc.write_text("# P\n\n**Stato:** attivo\n**Aggiornato:** 2026-01-05\n"
                   "**Prossimo passo:** Rileggere\n", encoding="utf-8")
    cfg = C.Config(roots=[F.Root(key="code", folder=str(root), host=str(root),
                                 prefix="~/", label="C", tags=())], language="en")
    app = create_app(cfg)
    client = app.test_client()
    client.environ_base["HTTP_X_FRONTSTEP_TOKEN"] = app.config["FRONTSTEP_TOKEN"]

    client.post("/project/code/prog/status?lang=en", json={"status": "done"})

    assert "**Stato:** concluso" in doc.read_text(encoding="utf-8")


def test_the_example_project_is_written_in_the_chosen_language(tmp_path):
    """Its document IS the tutorial: in Italian it has to be an Italian worked
    example, header included, or it teaches the convention in the wrong
    language."""
    root = tmp_path / "code"
    root.mkdir()

    F.create_example(str(root), language="it")

    text = (root / F.EXAMPLE_FOLDER / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    assert "**Stato:** attivo" in text
    assert "**Prossimo passo:**" in text


def test_the_tutorial_carries_both_languages_whichever_was_chosen():
    """The example is the only project on the page after a first run, so it is
    also the first thing the language switcher gets tried on — and a document
    cannot follow the switcher, because a document's language is a fact about
    the file and not a preference. Carrying both is the answer: English first,
    with a line at the top saying the Italian is further down.

    Only the HEADER differs between the two assets: that one has to be in the
    language that was chosen, being the worked example of the convention. The
    body below it is copied, and copies drift — this is what makes the drift red
    rather than silent."""
    assets = Path(F.PACKAGE_DIR) / "assets"
    english = (assets / "example_status.md").read_text(encoding="utf-8")
    italian = (assets / "example_status.it.md").read_text(encoding="utf-8")
    note = "> **Le stesse istruzioni sono anche in italiano**"

    assert english[english.index(note):] == italian[italian.index(note):]
    for text in (english, italian):
        # the note comes before either language's instructions, not between them
        assert text.index(note) < text.index("## You are reading a card")
        assert "## In italiano" in text


def test_the_english_example_is_still_the_fallback(tmp_path):
    """An unknown language gets the English tutorial rather than no project at
    all — an empty dashboard is the worse failure."""
    root = tmp_path / "code"
    root.mkdir()

    F.create_example(str(root), language="de")

    assert "**Status:** active" in (root / F.EXAMPLE_FOLDER / "CURRENT_STATUS.md").read_text()
