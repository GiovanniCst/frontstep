# Frontstep

**Status:** active
**Updated:** 2026-08-15
**Next step:** Put the least used tags behind an "others" so the filter bar loses a row on a phone
**Waiting for:**
**App:** Frontstep
**Tags:** oss
**Description:** One page with the state of every project you have, derived from a file your agent keeps up to date

## About

This file is two things at once, and that is the point.

It is the **status document of Frontstep itself** — the dashboard reads it like any other, so the
project shows up on its own page. And it is the **worked example of the convention**: the header
above is exactly what `docs/CONVENTION.md` describes, written by hand once and then kept up to date
by an agent, which is how every other project's is meant to work.

Looking for what Frontstep is and how to run it? That is `README.md`. Looking for the format of this
header? That is `docs/CONVENTION.md`. Looking for what changed and when? `CHANGELOG.md`.

## What it does, in one paragraph

It scans the folders you declare, reads one Markdown file per project, and derives a single page
from them on every request: three sections by who holds the ball, a card per project, and a
logarithmic silence line showing how long the quiet tail has grown. No database. Everything it can
write is listed in the README under *What the page can write*, and `writable = false` turns all of
it off in the routes, not just in the buttons.

## How it is checked

| | |
|---|---|
| Tests | 613 — the parser, the writes, the routes, what may be run, the stylesheet and the colour contrast |
| Python | 3.11 and up; CI runs 3.11, 3.12, 3.13 and 3.14 |
| Systems | the suite runs on Linux, Windows and macOS; the README's install lines run on Debian 13, Ubuntu 24.04, Fedora, Arch, openSUSE and Alpine |
| Layout | measured at 375, 390 and 768 px, not declared responsive |
| Colour | contrast computed from the stylesheet's own tokens, in both themes |

## Known limits

- **The filter bar is five rows at 375 px.** Readable, and every target is 24 px or more, but it is
  the tallest thing standing between the top of the page and the first card. Putting the least used
  tags behind an "others" would take a row out; nobody has built it.
- **The ticks of the silence line are 19 px wide**, under the 24 of WCAG 2.5.8. That is the
  *Essential* exception, documented where the rule is: the ticks sit logarithmically and crowd
  together on the right, so wider boxes would overlap and a tap would land on the neighbour. They
  stay reachable by keyboard, by scrolling and by the search box.
- **There is no way to ask a system which terminal it prefers, on macOS or outside Debian.** The
  editor asks everywhere — `xdg-open`, `open -t`, `start` — and so does the terminal on Windows and
  on Debian-like Linux, where `x-terminal-emulator` is that question in symlink form. Elsewhere the
  terminal a desktop installed with itself is named instead, which is still what is there for
  certain rather than what somebody happens to like: Ptyxis, GNOME Console, gnome-terminal,
  konsole, xfce4-terminal, mate-terminal, xterm. A terminal outside that list needs one line of
  configuration, and `frontstep doctor` says when there is none. `xdg-terminal-exec` would close
  the question properly and is left out until it is actually widespread — measured on Fedora 2026,
  it is not installed there either.
- **Opening a Linux file with a Windows program prompts, under WSL.** The document lives at
  `\\wsl.localhost\…` as far as Windows is concerned, so an editor may ask whether the origin is
  trusted. Nothing on this side can prevent it.
- **Setting up in a container writes the container's paths.** The folders the page offers are the
  ones it can see, so they are only right if what you mounted is mounted at the same place.
- **A button that opens something cannot promise a window appeared.** The server reports what it
  managed to START, and an operating system that refuses to create the process afterwards does so
  where nothing can see it. `frontstep doctor` names the programs it would use, which is the closest
  thing to an answer available before pressing anything.

## Conventions this project holds itself to

- **English everywhere**, code and comments included. The Italian fixtures in the tests are the
  exception, and a deliberate one: they are the documents the bilingual parser has to keep reading,
  and translating them would silently stop testing that.
- **Writing follows the document.** A file written in Italian stays Italian, down to the exact field
  name it uses. One codebase, no migration.
- **Every write into a status document goes through `_apply_to_header`.** The writes that create a
  file rather than editing one — the configuration, a new project, `AGENTS.md`, the skill — are
  each behind their own key, for reasons the three header writes do not need.
- **Nothing that arrives over HTTP becomes part of a command.** Not escaping: a design in which no
  string is ever parsed. The path lands in a single element of an argv list — alone, or after a
  flag's `=` — and nothing between there and the process splits it again; the route picks between
  two commands rather than receiving one.
- **Measured, not declared.** Layout is checked in a browser and colour is computed from the tokens;
  what has not been measured is said to be unmeasured.

## If something is not right

`frontstep doctor` says what this machine has and what it is missing: the Python version, whether
the command can be typed or needs its folder added to PATH, where the configuration is
or would go, whether the port is free, which roots hold projects, and which programs the Terminal
and Editor buttons would open. It exits non-zero only for what actually stops it working.

`CONTRIBUTING.md` before sending a patch, `CHANGELOG.md` for what changed.
