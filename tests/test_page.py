"""The stylesheet and the markup, checked against each other.

Jinja does not fail at compile time and neither does CSS: rename a class in a
template and the rule that styled it goes on existing, styling nothing. Nobody
finds out until they look at the page, and by then the change is three commits
old. It has already happened here — translating the project into English renamed
nine classes in the markup and left nine dead rules behind, and the cards lost
the background colour that says which section they are in.

These are not tests of how the page looks. They test the only thing that can be
tested without a browser: that the two files still talk about the same names.
How it LOOKS is measured in a browser, and no assertion here pretends otherwise.
"""
import re
from pathlib import Path

import pytest

from frontstep import core as F

STATIC = Path(F.PACKAGE_DIR) / "static"
TEMPLATES = Path(F.PACKAGE_DIR) / "templates"

def without_comments(text: str) -> str:
    """Comments do not style and do not render, so they must not count as use.

    They also say the opposite on purpose: a comment naming a Font Awesome 6
    icon exists precisely to warn that it renders nothing here, and a check that
    took it for a use would let the mistake through.

    Only BLOCK comments and full-line `//` are removed: a `//` in the middle of a
    line is `frontstep://` far more often than it is a comment.
    """
    text = re.sub(r"\{#.*?#\}", " ", text, flags=re.S)      # Jinja
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)     # HTML
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)      # CSS and JS
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)      # JS, whole line


# Comments are stripped from the STYLESHEET too, and not only from the markup:
# a comment mentioning `tests/test_contrast.py` had this file reporting `.py` as
# a class nobody writes. The rule is the same on both sides — what is commented
# out neither styles nor renders, so it cannot count as either.
CSS = without_comments((STATIC / "frontstep.css").read_text(encoding="utf-8"))
# Everything that can carry a class name: the templates write them, the JS
# writes some of its own into innerHTML and toggles others.
MARKUP = without_comments("\n".join(
    p.read_text(encoding="utf-8") for p in
    [*sorted(TEMPLATES.glob("*.html")), STATIC / "frontstep.js"]))


def _mentions(name: str) -> bool:
    return bool(re.search(r"(?<![a-zA-Z0-9_-])" + re.escape(name) + r"(?![a-zA-Z0-9_-])",
                          MARKUP))


def test_every_styled_class_is_a_class_something_writes():
    """A rule nobody can match is either dead weight or a rename that went half
    way — and the second one is a silent visual regression."""
    styled = sorted(set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", CSS)))

    assert [c for c in styled if not _mentions(c)] == []


def test_the_stylesheet_knows_the_real_section_names():
    """`.group[data-group="…"]` is what gives a card the paper colour of its
    section. The names come from `SECTIONS` in the code, and when those were
    translated this selector was not: three rules matched nothing and every card
    on the page went plain."""
    in_css = set(re.findall(r'data-group="([^"]+)"', CSS))

    assert in_css <= {key for key, _, _ in F.SECTIONS}


def test_the_stylesheet_knows_the_real_status_names():
    in_css = set(re.findall(r'data-status="([^"]+)"', CSS))

    assert in_css <= set(F.STATUS_ORDER)


def test_no_colour_is_used_without_being_defined():
    """A `var(--x)` with no declaration falls back to nothing: the property is
    dropped and the element inherits, which usually looks *almost* right."""
    used = set(re.findall(r"var\((--[a-z0-9-]+)", CSS))
    declared = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", CSS, re.M))

    assert sorted(used - declared) == []
    # and the other way round: a token nobody reads is a colour decision that
    # stopped being applied without anyone noticing
    assert sorted(declared - used) == []


@pytest.mark.parametrize("path", sorted(TEMPLATES.glob("*.html")) +
                                 [STATIC / "frontstep.js", STATIC / "frontstep.css"])
def test_the_icons_are_font_awesome_5_names(path):
    """The bundled subset is Font Awesome **5**. A 6 name renders nothing at all
    — the button stays an empty box, which is exactly the kind of breakage that
    survives a review."""
    available = set(re.findall(r"\.(fa-[a-z0-9-]+):before",
                               (STATIC / "fontawesome.css").read_text(encoding="utf-8")))
    text = without_comments(path.read_text(encoding="utf-8"))
    # `fa-spin`, `fa-fw` and friends are modifiers, not glyphs: they have no
    # :before rule and are matched by their own classes.
    modifiers = {"fa-spin", "fa-pulse", "fa-fw", "fa-border", "fa-li", "fa-lg",
                 "fa-xs", "fa-sm", "fa-1x", "fa-2x", "fa-3x"}
    used = {n for n in re.findall(r"\bfa-[a-z0-9-]+", text)} - modifiers

    assert sorted(used - available) == []


# ---- the page's half of the write defence ----------------------------------
#
# The routes refuse a write that carries no token, and that is the barrier. This
# is the other half: that the PAGE actually sends one. Nothing in Python can
# notice a `fetch` written by hand next to `write()` — it would simply start
# answering 403, on the one path nobody exercises twice.

def test_no_post_leaves_without_the_token():
    """Every `method: "POST"` in the script has to have the token header with
    it, which today means: they all go through `write()`.

    The mistake this catches is a `fetch` written out by hand next to the helper
    — it would look right, read right, and start answering 403 on the one path
    nobody exercises twice. The window is the object literal the two keys share.
    """
    js = without_comments((STATIC / "frontstep.js").read_text(encoding="utf-8"))
    from frontstep import web

    bare = [js[i:i + 60].replace("\n", " ")
            for i in (m.start() for m in re.finditer(r'method:\s*"POST"', js))
            if web.HEADER_TOKEN not in js[i:i + 250]]

    assert bare == [], "a POST that carries no token: " + "; ".join(bare)


def test_the_helper_sends_the_header_the_routes_ask_for():
    """The header name is agreed between two files that cannot import each
    other, so it is spelled out in both and checked here."""
    from frontstep import web

    js = (STATIC / "frontstep.js").read_text(encoding="utf-8")

    assert f'"{web.HEADER_TOKEN}": TOKEN' in js


def test_the_page_and_the_script_agree_on_where_the_token_is():
    """The `<meta>` the server renders and the selector the script reads: two
    strings in two files, and a typo in either is a page that cannot write."""
    page = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "frontstep.js").read_text(encoding="utf-8")

    assert '<meta name="frontstep-token"' in page
    assert 'meta[name="frontstep-token"]' in js


def test_the_path_on_a_card_ends_the_way_that_system_writes_paths():
    """The prefix was made system-aware and the trailing separator was not,
    which on Windows produced `%USERPROFILE%\\Documents\\name/` — a path correct
    everywhere except its last character. It now comes from the prefix."""
    card = (TEMPLATES / "_card.html").read_text(encoding="utf-8")

    assert '<span class="path-root">/</span>' not in card
    assert "{{ p.prefix[-1] }}" in card


def test_the_silence_explanation_owns_its_line_whatever_the_language():
    """Measured in a browser: it used to sit beside the title and drop below it
    only when the two together did not fit. `Silence line` left room and the
    sentence stayed alongside; `Linea del silenzio` did not and pushed it down —
    22px of header against 52px, and the whole section 29px taller in one
    language than in the other.

    A layout that depends on how long a word is in the language being read is a
    layout that a third language rearranges. `flex-basis: 100%` makes the break
    a decision. This cannot be checked by rendering — only a browser lays out —
    so what is checked is that the rule is still there.
    """
    assert re.search(r"\.silence-hint\s*\{[^}]*flex-basis:\s*100%", CSS)


def test_every_source_file_says_what_it_is_and_whose_it_is():
    """The two lines the License's appendix asks to attach to the work itself.

    `LICENSE` and `NOTICE` cover the project as a whole; this covers a FILE that
    travels on its own, which is how source usually moves — copied into a gist,
    an answer, another repository. Without it `core.py` on its own says nothing
    about who wrote it or what may be done with it, while `NOTICE` spends a
    paragraph on where attribution has to appear.

    Checked rather than remembered, because a new file is exactly where it would
    be forgotten.
    """
    package = Path(F.PACKAGE_DIR)
    files = sorted(package.glob("*.py")) + [package / "static" / "frontstep.js",
                                            package / "static" / "frontstep.css"]

    missing = [f.name for f in files
               if "SPDX-License-Identifier: Apache-2.0" not in
               f.read_text(encoding="utf-8")[:200]]

    assert not missing, (
        f"no licence header in: {', '.join(missing)} — two lines at the top, "
        "see CONTRIBUTING.md")


def test_the_readme_does_not_show_a_version_that_has_been_left_behind():
    """The README prints what `serve` says on a first run, version number and
    all, and it sat at 0.1.0 for six releases — nobody looks at a sample output
    they have read before.

    Checked rather than remembered: a sample that quietly stops matching what
    the program says is how a page starts lying about the thing it documents.
    """
    from frontstep import __version__

    readme = (Path(F.PACKAGE_DIR).parent.parent / "README.md").read_text(encoding="utf-8")

    stale = [v for v in re.findall(r"Frontstep (\d+\.\d+\.\d+)", readme)
             if v != __version__]
    assert not stale, (
        f"the README shows Frontstep {', '.join(stale)} while this is "
        f"{__version__} — update the sample output")


def test_every_window_closes_at_the_far_end_of_its_title_bar():
    """Every window keeps its close at the far end of the title bar. Checked as
    a rule about the markup, since only a browser lays out: a close button inside
    a `.doc-head` carries `doc-close`.
    """
    page = without_comments((TEMPLATES / "index.html").read_text(encoding="utf-8"))

    heads = re.findall(r'<form[^>]*class="doc-head"[^>]*>(.*?)</form>', page, flags=re.S)
    assert heads, "no heading closes a window any more — has the markup moved?"
    for head in heads:
        assert 'class="doc-close' in head, (
            "a window's close button is not a .doc-close, so nothing places it: "
            f"{head.strip()[:120]}")


def test_the_close_in_a_heading_sits_in_the_flex_line_not_over_it():
    """⚠️ `.doc-close` alone is not enough: it is `position: absolute` measured
    from `.doc-head`, which bleeds past the window — on a phone that put the only
    way out off the screen. Inside a heading it goes back into the flex line.
    """
    assert re.search(r"form\.doc-head\s*\{[^}]*display:\s*flex", CSS)
    assert re.search(r"form\.doc-head\s+\.doc-close\s*\{[^}]*position:\s*static", CSS)
    assert re.search(r"form\.doc-head\s+\.doc-close\s*\{[^}]*margin-left:\s*auto", CSS)


def test_a_window_title_starts_where_the_text_under_it_starts():
    """One measure read by the heading and by the body: a title and the text it
    titles cannot drift apart if neither owns the number. Nothing inside a window
    hard-codes an inset.
    """
    assert re.search(r"\.doc\s*\{[^}]*--doc-pad-x:", CSS), "the shared inset is gone"

    for rule in ("doc-scroll", "skill-body"):
        block = re.search(rf"\.{rule}\s*\{{([^}}]*)\}}", CSS)
        assert block, f".{rule} no longer exists"
        assert "var(--doc-pad-x)" in block.group(1), (
            f".{rule} sets its own horizontal padding again — it will drift from "
            "the heading above it")

    # And the heading of a form window must not bleed: it has nothing to cancel.
    block = re.search(r"form\.doc-head\s*\{([^}]*)\}", CSS).group(1)
    assert "margin-left: 0" in block and "margin-right: 0" in block
    assert "padding-left: var(--doc-pad-x)" in block


def test_the_topbar_controls_wrap_instead_of_widening_the_page():
    """A parent that wraps does not make its child wrap: `.topbar` wrapped and
    `.topbar-ctl` stayed one rigid row, pushing the page wider than the screen.
    """
    assert re.search(r"\.topbar-ctl\s*\{[^}]*flex-wrap:\s*wrap", CSS)
