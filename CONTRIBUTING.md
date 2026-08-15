# Contributing

## What this project is trying to be

One page, derived from files, that nobody has to update by hand. Most of the
decisions in here follow from that, and the two that matter most for a patch:

- **Frontstep writes in other people's files**, and every place it does is
  listed in the README under *What the page can write*. A new one is a design
  discussion before it is a pull request. Three of them rewrite a line of a
  status document and all three go through `_apply_to_header` in `core.py`:
  atomic, keeping the file's owner, permissions, line endings, language and
  field names. The others create a file rather than editing one — the
  configuration, a new project, `AGENTS.md`, the skill — and none of them
  overwrites what somebody else wrote.
- **The status document belongs to whoever wrote it.** A file written in Italian
  stays Italian after Frontstep changes its status; someone who wrote
  `Last updated` does not find `Updated` there afterwards. Every change to the
  writing path needs a test proving this still holds.

## Running it

```bash
uv venv --python 3.13
uv pip install -e . --group dev
.venv/bin/python -m pytest tests/ -q
```

Try it without touching anything real:

```bash
SB=/tmp/sandbox && mkdir -p $SB/code/{alpha,beta}
.venv/bin/frontstep init --config $SB/config.toml --root "$SB/code:Code:work"
FRONTSTEP_CONFIG=$SB/config.toml .venv/bin/frontstep serve
```

```powershell
# the same on Windows
$SB = "$env:TEMP\sandbox"; mkdir "$SB\code\alpha", "$SB\code\beta" -Force
.venv\Scripts\frontstep init --config $SB\config.toml --root "$SB\code:Code:work"
$env:FRONTSTEP_CONFIG = "$SB\config.toml"; .venv\Scripts\frontstep serve
```

Python 3.11 is the floor — that is where `tomllib` arrived. The CI runs **3.11,
3.12, 3.13 and 3.14 on Ubuntu, and 3.11 and 3.14 on Windows and macOS**, plus
the README's own install instructions executed on Debian 13, Ubuntu 24.04,
Fedora, Arch, openSUSE and Alpine.

Windows and macOS are not decoration there: the first time they ran this suite,
48 tests failed on one and 3 on the other, and three of those were real defects.
If you are adding a test, ask what it assumes about the machine under it — a
home folder is not always `$HOME`, `/srv/repos` is not always a path, and a
filesystem does not always tell `a` from `A`. `tests/conftest.py` has helpers
that ask instead of assuming.

## Tests

Green before and after, always. Beyond that, three habits worth knowing:

- **The Italian fixtures stay Italian.** They are the documents the bilingual
  parser has to keep reading, and translating them would silently stop testing
  the thing they exist for.
- **Never edit an assertion to make a change pass.** An assertion encodes an
  invariant wider than its own surface; rewriting it retires that invariant in
  silence. Show the old invariant no longer holds first.
- **The page has tests that are not about how it looks:** `test_page.py` keeps
  the stylesheet and the markup talking about the same names, and
  `test_contrast.py` computes WCAG ratios from the declared colour tokens. If
  you rename a class or add a colour, those are the two that will tell you.

## Changing the page

CSS and Jinja fail silently — a renamed class does not raise, it just stops
applying. Two rules follow:

1. run the tests above, which catch the structural half;
2. **measure the other half in a browser**, and say what you measured. "Looks
   fine" is not a result. The mobile numbers this project holds itself to are in
   the responsive block of `frontstep.css`, with what they were before.

## Style

- **English everywhere**, code and comments included. `docs/GLOSSARY.md` maps
  the terms.
- Comments say **why**, not what. The what is already in the line below.
- No new dependency without a reason that outlives the convenience: this thing
  installs with Flask, mistune and the standard library, and that is a feature.
- Commit messages in the imperative: *Add X*, *Fix Y*.

## The convention itself

`docs/CONVENTION.md` is the one place the status-document format is defined. The
agent skill, the `AGENTS.md` block and the example document are **faces of it,
not copies** — change the convention and the three follow, in the same commit.

## The name

The code is Apache-2.0. The name is not covered by it: see `TRADEMARK.md` before
naming a fork. Contributions are accepted under the same License as the project.

Every source file carries the two-line header the License's appendix asks for,
so a file that travels on its own still says what it is:

```python
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
```

A new file gets it too. `NOTICE` is the other half of the same obligation, and
it is not a formality — read it before removing anything from a fork's footer.
