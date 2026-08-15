"""Colour contrast, computed from the stylesheet's own tokens.

The palette used to carry a comment admitting it had been chosen by eye and
never measured. This file is what replaced that comment: the ratios are computed
from the declared hex values with the WCAG formula, so a colour cannot be
changed back below the line without a test going red.

**What is measured and what is not.** These check the pairs the page actually
puts on top of each other — the ratio is a fact about two hex values, and that
much is exact. They say nothing about whether the page LOOKS right: that is
measured in a browser, and it is a different question.

Thresholds, from WCAG 2.1:
  * 4.5:1 for text — everything here is small text, so nothing gets the 3:1 of
    large text;
  * 3:1 for a mark that carries meaning without being read (a tick, a border).
"""
import re
from pathlib import Path

import pytest

from frontstep import core as F

CSS = (Path(F.PACKAGE_DIR) / "static" / "frontstep.css").read_text(encoding="utf-8")

TEXT = 4.5
MARK = 3.0


def _tokens(selector: str) -> dict[str, str]:
    """The colour tokens declared in one `:root` block.

    A token may be declared as another one (`--ink-alert: var(--st-undeclared)`),
    which is a real thing the stylesheet does to say "the same colour, used for
    something else". Those are followed, or the pair being measured would be the
    one nobody sees.
    """
    start = CSS.index(selector)
    body = CSS[start:CSS.index("}", start)]
    declared = dict(re.findall(
        r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,6}|var\(--[a-z0-9-]+\))\s*;", body))
    return declared


def _resolve(tokens: dict[str, str]) -> dict[str, str]:
    """Follow `var(--x)` down to the hex it stands for."""
    out = {}
    for name, value in tokens.items():
        seen = set()
        while value.startswith("var(") and name not in seen:
            seen.add(name)
            value = tokens[value[4:-1]]
        out[name] = value
    return out


# The light theme redeclares only what changes: everything else is inherited,
# and comparing a light background with a dark theme's ink would measure a pair
# that never appears on screen. Aliases are resolved AFTER the merge, because an
# alias in the base block can point at a token the light theme overrides.
_DARK_RAW = _tokens(":root {")
DARK = _resolve(_DARK_RAW)
LIGHT = _resolve({**_DARK_RAW, **_tokens(':root[data-theme="light"] {')})
THEMES = {"dark": DARK, "light": LIGHT}


def luminance(value: str) -> float:
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)

    def channel(pair: str) -> float:
        c = int(pair, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return (0.2126 * channel(h[0:2]) + 0.7152 * channel(h[2:4]) + 0.0722 * channel(h[4:6]))


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return round((max(la, lb) + 0.05) / (min(la, lb) + 0.05), 2)


def test_the_formula_agrees_with_the_two_ends_of_the_scale():
    """A contrast function that is wrong makes every other test here pass for
    nothing, so it is pinned to the two values everyone knows."""
    assert contrast("#000000", "#ffffff") == 21.0
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


# The surfaces a card can sit on. `--surface` is the card's own background and
# the three papers override it per section: any of them can be behind a badge.
BACKGROUNDS = ("--surface", "--paper-open", "--paper-paused", "--paper-closed")


@pytest.mark.parametrize("theme", sorted(THEMES))
@pytest.mark.parametrize("index", range(F.TAG_COLORS))
def test_the_app_name_reads_on_its_band(theme, index):
    """The band carries the app name, so the tag colour is a TEXT background."""
    t = THEMES[theme]

    assert contrast(t["--band-ink"], t[f"--tag-{index}"]) >= TEXT


@pytest.mark.parametrize("theme", sorted(THEMES))
@pytest.mark.parametrize("index", range(F.TAG_COLORS))
@pytest.mark.parametrize("background", BACKGROUNDS)
def test_a_tag_badge_reads_on_every_card(theme, index, background):
    """A tag is text twice over: the band is only the first time. In the footer
    the tag writes itself, in its own colour, on the paper of its section — and
    that is the pair four of the eight light hues were failing."""
    t = THEMES[theme]

    assert contrast(t[f"--tag-{index}"], t[background]) >= TEXT


@pytest.mark.parametrize("theme", sorted(THEMES))
@pytest.mark.parametrize("ink", ["--ink", "--ink-2", "--ink-3", "--ink-desc",
                                 "--ink-waiting-box", "--ink-alert"])
@pytest.mark.parametrize("background", BACKGROUNDS + ("--plane", "--surface-2"))
def test_every_ink_reads_on_every_surface(theme, ink, background):
    """The greys of the hierarchy are not decoration: project titles, dates and
    descriptions are written in them, and `--plane` is darker than the panels —
    a token that clears the panels can still fail the page behind them."""
    t = THEMES[theme]

    assert contrast(t[ink], t[background]) >= TEXT


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_the_selected_pill_reads(theme):
    """`--accent-solid` is the accent as a text BACKGROUND — a selected filter,
    the primary button. It exists apart from `--accent` for exactly this."""
    t = THEMES[theme]

    assert contrast(t["--accent-ink"], t["--accent-solid"]) >= TEXT


@pytest.mark.parametrize("theme", sorted(THEMES))
@pytest.mark.parametrize("status", ["--st-active", "--st-waiting", "--st-paused",
                                    "--st-done", "--st-undeclared"])
def test_the_status_marks_stand_out_from_the_page(theme, status):
    """These are marks, not text: the ticks of the silence line and the section
    dots. 3:1 is the bar, and they are measured against the page plane, which is
    what the silence line sits on."""
    t = THEMES[theme]

    assert contrast(t[status], t["--surface"]) >= MARK
