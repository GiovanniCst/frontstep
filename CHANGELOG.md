# Changelog

Notable changes to Frontstep. Format follows [Keep a Changelog](https://keepachangelog.com/1.1.0/),
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.2]

### The four the last release left on the list

0.5.1 closed what the review found and wrote down four things it did not. They
are closed here, and each was reproduced before being fixed.

- **A folder name could become a command, on WSL.** It is the one place where
  "argv is a list, so nothing is parsed" stopped being true: the argv reaches
  `cmd.exe`, and the interop layer rebuilds a command line that cmd parses
  again — so a `"` in the name closed the quoting and what followed ran as a
  second command. Such a path is now refused, which takes away nothing: `"` is
  legal in a POSIX folder name and forbidden in a Windows one.
- **A failed write was reported as a missing header line.** Both came back as
  the same `400 No status line to change`, and the first sends whoever reads it
  to check a header that is perfectly fine. They are now two answers: `400` for
  a line that is not there, `500` naming the write that failed.
- **`writable = false` did not always turn off opening programs.** It does when
  the configuration comes from a file, and did not when a `Config` was built in
  Python — so a dashboard that was read-only by construction still started
  terminals. "Not said" is now a value of its own, resolved once.
- **A non-UTF-8 `AGENTS.md` took down the project that was being created.**
  `UnicodeDecodeError` is a `ValueError`, so it went straight past the `except`
  written to report exactly that: the route answered 500 with the folder and the
  document already on disk. The failure is reported next to the project now.

## [0.5.1]

### Three ways a write could damage the document it was editing

Found by reviewing this release rather than by anybody losing a file, and each
one measured before and after:

- **A document that is not UTF-8 was rewritten as mojibake.** It is read with
  `errors="replace"` so the page can show it; that replaced text was then
  written back, so every byte that could not be decoded became U+FFFD **on
  disk**, in the whole file, and the route answered 200. A `CURRENT_STATUS.md`
  saved by a Windows editor in cp1252 is not a laboratory case. Such a file is
  now refused, and not one byte of it changes.
- **Every line ending was rewritten.** A CRLF document came back all LF, so
  changing one line showed up as a whole-file diff. The file keeps its own.
- **A header shown inside a code fence was written into.** A document that
  demonstrates the format before declaring it had the EXAMPLE rewritten while
  the real header never changed — so the card kept showing the old status and
  each click damaged another line. Fences are skipped, and the search stays in
  the same 40-line head the card reads.

Also on the write path: a status document that is a **symlink** was replaced by
a plain file, leaving the real one behind with the old contents; and the
temporary file had a fixed name, so two concurrent writes could overwrite each
other in the one place where that loses a document.

### The container never worked, and now does

`create_app()` with no argument means *setup*, not *find the configuration* — so
the image ignored the config mounted next to it and served the onboarding page
forever. That page needs the key `serve` prints, and a WSGI server never runs
`serve`: the key existed nowhere, and the container answered 403 for good.

There is a **container section** in the README now, and its instructions were
executed from a clean clone rather than described. Two of them were wrong until
they were: `init` writes its configuration somewhere else unless told, and
Docker turns a missing mount source into a *directory*.

### Said plainly, after checking

The pages that describe this program were measured against it, and several
claims did not survive:

- **what it writes.** Three documents said "four places". Counting them gives
  more — the skill in `~/.claude/skills/`, `AGENTS.md`, the folder a new project
  gets. The README now lists every one, with where it lands, and says that
  `writable = false` turns all of them off in the routes.
- **the terminal.** It claimed no program is named anywhere in the code. One is,
  on macOS and on every Linux that is not Debian-like — there is nothing to ask
  there, so what the desktop shipped with is opened by name.
- **the CI.** It does not run the suite on six distributions; it installs from
  the README's own lines there, and runs the suite on Ubuntu, Windows and macOS.
- **the fallback when the command is not on PATH.** `python -m frontstep` does
  not work after `uv tool install`, which is the install this page recommends.

The **Editor button no longer falls back to a `vscode://` link**. From a page the
only way to start a program is a registered URI scheme, and none of them means
"whatever this system opens `.md` with": naming one editor for everybody is the
opposite of what that button is for. Where the server cannot open one, the button
is gone and **Path** — which always works — stays.

### Fixed

- `?key=é` was a 500 with a traceback: `compare_digest` raises on non-ASCII.
- A folder name reached the page's `innerHTML` twice — directly, and through the
  server's error message — carrying whatever the folder was called.
- `skill --install agents --target <folder>` wrote one level **above** it.
- `adopt --status` did not list `done` among its values, while accepting it.
- An index line only matched a project under a literal `~/projects/`, so an index
  written by anybody who keeps their projects elsewhere matched nothing at all.
- `scripts/fetch_fonts.py` wrote into a `static/` folder that has not existed
  since the package moved under `src/`.

## [0.5.0]

### It runs where people actually are

This is the release where "works on Windows and macOS" stops being a hope. Both
had never run a line of this suite until a few days ago; 0.4.5 put them into the
CI, 0.4.6 and 0.4.7 fixed what they said, and every job is now green:

| | |
|---|---|
| Ubuntu | 3.11, 3.12, 3.13, 3.14 |
| Windows, macOS | 3.11 and 3.14 — the two ends of the range |
| Installed from the README's own lines | Debian 13, Ubuntu 24.04, Fedora, Arch, openSUSE, Alpine, Windows, macOS |

Three defects came out of it, all of them things no amount of testing on one
system could have found: `✓` is not in cp1252 and took `doctor` down on its
first line, a host path was joined with a `/` that Windows does not write, and
`init --root` cut `C:\Users\me\code` at the drive letter — which made the
non-interactive install unusable on that system.

### The README says what it is asking you to run

The install section is now **Install with uv, the easiest path**, and each line
in both blocks carries a comment saying what it does — the paragraph underneath
described "the first line" and left the other two unexplained.

It also says, plainly, what `curl … | sh` and `irm … | iex` actually are: a
script downloaded from `astral.sh` and executed without being saved or shown to
you. Astral — who make uv, Ruff and ty — [joined
OpenAI](https://openai.com/index/openai-to-acquire-astral/) in March 2026, so
that is who is being trusted for the length of that line. Worth knowing before
running it, not after.

A new **Other ways in** section for people who would rather not: uv from
Homebrew, WinGet or pipx; a virtual environment of your own; a clone; Docker.
The venv route carries the warning the others do not need — it builds on the
system Python, and on a machine running 3.10 it stops with "requires a different
Python", which is what it did when it was tried.

The sample output in the README now has a test holding it to the real version
number. It had been showing 0.1.0 for six releases. The screenshots were a
release behind too — the palette still had the red that came out on 15 August,
and the top bar predated the two skill buttons.

Nothing changed in what the dashboard shows or writes.

## [0.4.7]

### `init --root` could not take a Windows path

`--root` separates the folder from its label with a colon, and
`C:\Users\me\code` carries one of its own before ours: the split registered a
root called `C` and labelled it `\Users\me\code`. So the non-interactive
`init` — the one a script or an installer calls — could not accept any local
path on that system. The drive is taken off before the split and put back
after, and UNC paths (`\\server\share\…`) come through whole too.

0.4.6 took Windows from 48 failing tests to 21 and macOS to none; this takes
the rest, and what was left was one more defect and a dozen more assumptions of
the same kind — that a relative path can be printed with a `/` in it, that
`start_new_session` means something everywhere, that `/srv/repos` is a path.
Where a check genuinely cannot exist on a system it now says so out loud and
skips, rather than passing by accident or failing forever.

## [0.4.6]

### The first time this ran on a machine nobody here owns

0.4.5 put Windows, macOS and six distributions into the CI, and this is what
they said. The installation held everywhere — all six distributions, both
desktops, `uv` bringing its own Python exactly as the README promises. The
suite did not: 48 of 592 tests failed on Windows, 3 on macOS.

**Two were defects, and both were ours.**

- **`✓` is not in cp1252, and the CLI prints it.** On a Windows console `doctor`
  died with `UnicodeEncodeError` on its first line — the command whose entire
  job is to report on a machine that is not working, failing hardest where it is
  needed most. `init`, `adopt`, `skill` and `serve` print the same symbols and
  would have gone the same way. Everything the CLI says now goes through one
  place that asks the STREAM what it can carry: a UTF-8 terminal still gets
  `✓ · ✗`, a cp1252 one gets `ok -- !!`, and a path in a script no codepage
  covers no longer silences the report.
- **A host path was built with a `/` in an f-string**, so on Windows the folder
  handed to a terminal came out `C:\Users\…\projects/prog`. It is now joined in
  the shape of the path itself — which is not the same question as the shape
  this machine uses, and cannot be, because in a container the host path belongs
  to somebody else's machine.

The other 46 were assumptions the tests had never written down, because on Linux
they are all true: that a home folder is `$HOME`, that an absolute path starts
with a slash, that a filesystem tells `a` from `A`, that a file has a mode, that
any name can be a folder name. Each is now asked as a
question about the thing it needs, and never about the name of the operating
system — `chmod` it and read it back is an answer, `sys.platform` is a guess.

Nothing in what the dashboard shows has changed.

## [0.4.5]

### Two buttons for the thing that makes it work

The skill is the engine, and until now the only way to install it was a command
in the README. There are now two windows on the page, next to **New project**:

- **Skill: Claude** — where `~/.claude` exists, one button writes the skill into
  it and says the exact path first. Where it does not, the window says so and
  hands over a prompt to paste into a Claude session: a machine without that
  folder is a machine that does not run Claude Code, and creating another
  program's configuration directory is not Frontstep's to do.
- **Skill: other agents** — `AGENTS.md` lives inside a project rather than in
  one place, so there is no single install. The window points at the checkbox on
  New project, and gives the prompt for a project that already exists.

The setup page offers the same thing at the one moment somebody is certainly
paying attention — again, only when `~/.claude` is already there.

`writable = false` refuses the install like every other write, and the button is
not shown when it would only fail.

### A new project can carry the agent instructions with it

"New project" now has a checkbox — off by default — that drops an `AGENTS.md`
in the folder being created. Off, because somebody running Claude Code installs
the skill once for the whole machine and does not need this file in every
project; the one who needs it knows they do. It is the file that makes the whole thing work:
every agent that opens that project reads it and knows to keep the status
document current.

**It never overwrites.** The folder may be one that was already there — "New
project" adopts a folder that has no status document — and its `AGENTS.md` may
have been written for somebody else's agent long before Frontstep turned up. So:
the file is created when there is none, our section is **appended** when there
is one, and on a later pass only the text between `<!-- frontstep:begin -->` and
`<!-- frontstep:end -->` is rewritten. Everything else in that file is left
exactly as it was, and three tests hold the line.

The writing itself moved into `core.write_agents_block`, shared with
`frontstep skill --install agents`: two ways in, one behaviour. That is the
lesson `create_example` taught when `init` had it and the page did not.

### The installation instructions were wrong for everybody

The first line of the README said `uv tool install frontstep`, and **that package
has never existed on PyPI** — anyone who copied it got an error, and the name
being free meant a stranger could have taken it and been installed in our place.
The fallbacks were no better: measured on stock images in August 2026, Debian 13
and Ubuntu 24.04 ship python3 with neither `pip` nor `ensurepip` (so
`python3 -m venv` refuses too), the Fedora and Arch base images have no Python at
all, and a Fedora live desktop has Python without `pip`.

There is now **one** way in, the same three lines on every system: install `uv`,
`uv tool install <url>`, `frontstep serve`. `uv` is a single static binary that
brings its own Python, which is why it is the same everywhere — verified by
running it on Debian, Ubuntu, Fedora, Arch and openSUSE, each starting from a
machine with no Python and no pip.

The section explaining how to install Python on Windows is gone with it: there
is nothing to install first any more.

### The CI runs on the three systems, and on six distributions

`pytest` on Ubuntu across 3.11→3.14, and on **Windows and macOS** at both ends of
that range — until now the suite had never run on either. A second job executes
**the README's own instructions** on Debian, Ubuntu, Fedora, Arch, openSUSE and
Alpine, and a third does the same on Windows and macOS: instructions nobody runs
are a promise, and this is what turns them into a test.

### README and the name

The page now opens with what the thing actually is — an agent skill that keeps a
`CURRENT_STATUS.md` current while it works, and a dashboard derived from those
files — and it mentions the two buttons on every card: a terminal already inside
the project's folder, and its document in your editor. A published fork now
**keeps the name Frontstep and adds its own** (`Frontstep-Evolution`,
`Go-Frontstep`), where before it was asked to pick a different name entirely: the
genealogy stays readable and the two builds stay told apart.

### The windows close where windows close, and the page fits a phone

The two skill windows above were the first thing built here that nobody had ever
looked at — rendered, covered by tests, never once opened in a browser. Opening
them found three defects that 588 tests did not, none of them about the skill:

- **The close button was at the wrong end of the title bar.** Three windows close
  through their heading, and all three put their `×` 3px after the title, 806px
  from the right edge where every window on the web keeps it. On a 375px screen
  it sat *past* the right edge — the only way out of a full-screen window, placed
  where it cannot be tapped. The window that reads a document had always done
  this correctly; the other three had copied the wrong markup.
- **The title was flush against the border**, 18px to the left of the very text
  it titled, 24px in New project. The heading is built to sit inside the scrolling
  body and bleed to the edges, so its negative margins cancel that body's padding;
  in these three it is a child of the dialog, which has no padding for it to
  cancel. One shared measure now, read by the heading and by the body under it.
- **The page scrolled sideways on a phone**: 592px of document on a 375px screen,
  the wordmark scrolled off and the language switch past the edge. The top bar
  wraps, the block of controls inside it did not.

Each was measured in the browser rather than eyeballed, and each of the four new
tests was checked to fail against the old code.

### Fixed

- **The Editor button said "the folder" and opened the file.** Every detection
  asks the system for the DOCUMENT — `xdg-open`, `open -t`, `os.startfile` all
  get `CURRENT_STATUS.md` — while the tooltip named the folder and showed the
  folder's path. Seen on Fedora the first time the button was pressed, when a
  text editor came up with the document in it. The tooltip now names whichever
  of the two the editor will actually be handed, and shows that path; a
  configuration using `{}` still says "the folder", because there it is one.

## [0.4.4]

### Opening a terminal works on a Linux desktop

Installed on a Fedora live image, `frontstep doctor` announced "nothing found on
this machine" for the terminal — from inside a perfectly good terminal. Two
separate defects, and neither could be seen from a machine where it already
worked:

- **The list did not know the terminals Fedora ships.** It tried
  `x-terminal-emulator` (which is Debian's), `gnome-terminal`, `konsole`,
  `xfce4-terminal`, `mate-terminal` and `xterm`; Fedora Workstation ships
  **Ptyxis**, and shipped **GNOME Console** (`kgx`) before it. Both are in the
  list now, with the flags taken from their own documentation and, for ptyxis,
  watched opening a window in the right folder.
- **Three of the terminals already in the list were passed a folder called
  `{}`.** The path was substituted only when the placeholder was a whole
  argument, so `gnome-terminal --working-directory={}` went through untouched.
  It now fills in wherever it sits, and the rule that actually matters — a path
  never becomes more than one argument, because a command is a list and nothing
  splits it again — is a test with spaces, quotes and semicolons in it.

`xdg-terminal-exec`, which would answer the question properly on any desktop,
is **still not on Fedora either**: leaving it out stays the right call, and that
is now measured on two distributions rather than one.

### Python 3.14

That live image runs 3.14, so it is what a user gets today rather than something
to get ready for. The suite passes on it and the CI runs it alongside 3.11, 3.12
and 3.13.

## [0.4.3]

### The tag palette has no red in it

Red is the one colour that means something on its own on a page about state, and
a tag had only to hash onto it for a perfectly healthy project to read as an
alarm — which is what the example project did in English, where its tag is
`example`. The palette is **seven** colours now.

Nothing took the eighth place, and that was measured rather than settled by
taste: with the red gone the widest gap left is between brass and green, and
every hue that fits there lands about ΔE 24 from its nearest neighbour once the
light theme darkens all of them — as close as the closest pair already there.
An eighth colour that cannot be told from a seventh is not a colour.

Seven colours re-deal every hash, so the collision the assignment exists to fix
moved: it used to be `work`/`personal`/`finance`, it is now `work`/`prod`. The
tests say so with the new pair, and `assign_colors` resolves it as before.

**A colour still never depends on the language of the page** — it comes from the
tag written in the document, and the switcher does not touch documents. That is
now a test rather than a property nobody had checked.

## [0.4.2]

### The tutorial carries both languages

The example project is the only card on the page after a first run, so it is
also the first thing the language switcher gets tried on — and a document cannot
follow the switcher: its language is a fact about the file, not a preference,
and the whole design rests on Frontstep coming back to a document in the language
it found it in. The tutorial now says both, English first, with a line at the top
pointing at the Italian below. Only the header still differs between the two, in
the language that was chosen: it is the worked example of the convention.

### Fixed

- **The status a screen reader hears is now translated.** The card shows its
  status as the colour of its paper, so that one line is the whole of it for
  anybody not seeing colour — and it announced the canonical value, `active`, in
  the middle of a page otherwise entirely in Italian. `t()` takes a context
  argument for it: `Paused` is a section title, plural in Italian, and also the
  state of a single card, singular.
- **Close and Pause said what they would do in English only.** Their tooltip was
  assembled by hand in the script — "Writes status done in the header of …" —
  with the canonical status inside it. One whole sentence per status now, from
  the catalogue: a phrase built from pieces only reads in the language it was
  written for.
- **What a button will open is translated**, where it describes something rather
  than naming a program: "the default Windows terminal" is a sentence, `kitty`
  and macOS's `Terminal` are names, and a name is the same word everywhere.
- **"1 giorni fa".** The silence line put a number next to a word; both forms
  now come from the catalogue, in both languages.

## [0.4.1]

**The silence line was a different height in each language.** Its explanation
sat beside the title and dropped below only when the two together did not fit,
so the layout depended on how long a word is in the language being read —
measured, `Silence line` left room and `Linea del silenzio` did not, giving 22px
of header against 52px and a section 29px taller in Italian. The explanation now
has a line of its own in every language.

## [0.4.0]

### The interface speaks Italian too

Frontstep read and wrote status documents in two languages from the start — a
file that says `**Stato:** attivo` stays that way, down to the field name — and
the interface around it spoke only English. Choosing Italian during setup
changed the documents and left every button, every label and **the tutorial
itself** in English, which reads as a setting that does nothing.

Now the page follows the language too, and there is a **switcher in the top
bar**. The language lives in the URL, like the staleness threshold: switching is
a navigation, so it survives a refresh and a page can be handed to somebody in
the language it was read in, without writing anything to the configuration.

The example project — whose document IS the tutorial — is written in the chosen
language, header included. An Italian tutorial with an English header would be
teaching the convention in the wrong language.

What is deliberately NOT translated: **the field names of a status document**
and the status values written to disk. Those are not interface, they are the
file's own vocabulary, and a document keeps its own language whatever the page
is being read in. Reading the dashboard in English and pressing Close on an
Italian project still writes `**Stato:** concluso`.

Missing translations fall back to English rather than failing: the English
string IS the key, so a template stays readable and a gap costs one sentence in
another language, not a broken page. A test keeps the catalogue and the markup
in step in both directions — no key asked for and missing, no translation left
orphaned.

## [0.3.2]

**A card's path ended in the wrong character on Windows.** The prefix had been
made system-aware and the trailing separator had not — it was a literal `/` in
the markup — so a path read `%USERPROFILE%\Documents\name/`: correct everywhere
except its last character. It now comes from the prefix, so there is one place
that decides how paths are spelled.

**The example project said it was made by `frontstep init`.** It is made on a
first run whichever way you come in, and since setting up in the browser it is
usually not `init` that made it.

## [0.3.1]

**`frontstep doctor` called a machine with no desktop broken.** A server or a CI
runner has no terminal and no editor installed, and is a perfectly good place to
run a dashboard: the page works and those two buttons are simply not on the
cards. The check marked that fatal and exited non-zero, which is the one thing
the exit code must not do — it is there to mean "this will not work", and a
missing button is not that. It now reports the two as worth knowing, and says
the buttons will be absent.

## [0.3.0]

### Fixed: installing on Windows, and the first run anywhere

**The application could be installed and not started.** `pip` puts the command in
the interpreter's scripts folder, which on Windows is very often not on PATH — it
warns about this and moves on. **`python -m frontstep` now works**, and needs no
PATH at all.

**Terminal opened nothing on Windows, and reported success.**
`cmd.exe /c start … cmd.exe` opens a terminal when typed at a prompt and opens
nothing when the same list is handed to `subprocess.Popen`, which reports success
because `cmd.exe` really did start. It now uses `CREATE_NEW_CONSOLE` with the
folder in `cwd`, and `os.startfile` for the editor: the API instead of a command
line to quote, hand to a shell and have parsed again. `start_new_session`, which
is POSIX-only and Windows ignores in silence, is gone with it — and with a
console of its own the process keeps its own streams, because `cmd.exe` reads
standard input and `DEVNULL` is end-of-input.

**A first run landed on an empty dashboard.** `frontstep init` had always created
an example project whose document is the tutorial; the setup page, which is now
the main way in, did not. The example is now created whichever way you come in.

**An empty dashboard blamed the filters.** It said *"No project matches these
filters"* with every filter at rest. It now says there is nothing to filter, and
what would change that.

**Nothing was ticked on the setup page.** The first suggestion was ticked only
where projects were already found, which on a first run is nowhere — so pressing
Start produced an error. The home folder also sorted first when every count was
zero, offering "scan your entire home directory" as the opening move; it now
sorts last.

**The configuration went to `~/.config` on every system.** That is a Unix
convention, in a home directory where no other Windows program writes. It now
goes to `%APPDATA%` on Windows and `~/Library/Application Support` on macOS;
`XDG_CONFIG_HOME` still wins wherever it is set. Cards showed `~/Documents/…`
too, and `~` means nothing on Windows: paths there now shorten to
`%USERPROFILE%` and use backslashes.

### `frontstep doctor`

```
frontstep doctor
```

Says what this machine has and what it is missing: Python's version, whether the
command can be typed, where the configuration is or would go, whether the port is
free, which roots hold projects, and which programs the two buttons would open.
Exits non-zero only for what actually stops it working.

Every check earns its place by having failed somewhere real. A doctor that lists
everything conceivable is read once and never again.

## [0.2.0]

Three things the buttons and the first run needed, and one nobody had asked for
— found while measuring the ground the other three would stand on.

### Setting it up happens in the browser

`frontstep serve` used to refuse to start without a configuration and name the
command that would create one — a list of questions asked in a terminal. For an
application whose entire interface is a page, that meant the page could not be
seen until the command line had been dealt with.

It now **starts**, prints one address, and asks there:

```
Frontstep 0.1.0 — not set up yet.

  Open this, and it will ask you where your projects are:

    http://127.0.0.1:9015/?key=…
```

The page offers the folders that are actually on the machine — `~/projects`,
`~/code`, the home folder — each with **how many folders inside already have a
status document**. That number is the point: it answers "is this the one you
meant?" with a fact rather than a folder name, and it is measured, not guessed.
Then it writes the configuration and **serves it straight away**, in the same
process. Nothing to restart.

The reasoning that produced the old behaviour is not discarded: a dashboard that
comes up pointing at some plausible folder looks broken, which is why none is
ever invented. A page that asks where to look is not that page.

`frontstep init` stays for anyone who would rather not use a browser. Both write
the same file through the same writer.

**The key in that address is not decoration.** This is the fourth place
Frontstep writes and the most dangerous: the file it produces decides `bind`,
`writable`, and which commands may be run. Whoever can read the terminal started
the program; on a machine with more than one account, being able to reach a port
is not the same thing. Without the key, any local account could point Frontstep
at somebody's home folder and switch on the commands that run programs. The
route also refuses once a configuration exists — it may only ever create the
first one — and the port it writes is read off the address the request arrived
at, so starting on another port because 9015 was taken does not leave you a
configuration naming a port nothing is listening on.

### Terminal and Editor work with nothing installed

Both buttons used to need something of yours to be true. **Terminal** went
through a `frontstep://` protocol handler you registered by hand, so out of the
box it did nothing. **Editor** was a `vscode://` link written into the code: on a
machine without a VS Code family editor it did nothing either, and said nothing
about it.

A page served over `http://` cannot start a program — that is the browser's
barrier — but **the server runs on the same machine as whoever is looking**, so
the buttons now ask it to.

**Frontstep does not choose a program.** It asks the system to open the thing,
the way double-clicking it would: `xdg-open` on Linux, `open` on macOS, `start`
on Windows — which also decides *which console* a terminal appears in, because
Windows has a "default terminal application" setting and `start` honours it. The
answer is a choice the user already made in their own settings.

That is stronger than defaulting to the program a system ships with. Naming
Notepad, or TextEdit, would override a choice the user has already made: plenty
of people have set something else as what opens a `.md`, and on those machines
the stock program is not the right answer — it is the same mistake as
hard-coding `vscode://`, one size down.

So no editor is detected at all: there is no list of favourites to maintain and
no argument about whose editor goes first. On Linux the terminal goes through
`x-terminal-emulator`, which is the same question in symlink form.

The button's title names the program it will open, which the link it replaces
could never do.

Name your own if the guess is wrong. A **list**, one argument per item — `{}` is
the project folder, `{file}` its status document:

```toml
terminal = ["kitty", "--directory", "{}"]
editor   = ["subl", "{}"]
launch   = false        # or: open nothing at all
```

`launch` defaults to whatever `writable` is — somebody who asked for a dashboard
that does not touch their files did not ask for one that runs programs — and
opening also requires `bind` to be a loopback address, whatever `launch` says. A
dashboard reachable from the network that starts a terminal on the machine it
runs on is a remote shell. In a container it is off for the same reason, and
nothing is lost: there is no terminal in there to open. Where it is off, both
buttons fall back to exactly what they were, so nobody loses what they had.

What keeps this from being a shell is not a check on the input: it is that
there is no input. The route takes no command — it picks between two commands
from the configuration — and the path is placed into an argv **list** as one
element, with no shell anywhere to re-split it. A project folder called
`; rm -rf ~` is a folder with a silly name, and there is a test for each way of
spelling one.

### Security

Binding to `127.0.0.1` was being relied on as though it made the dashboard
private. It does not: the loopback interface is reachable by every page the
browser has open and by every other account on the machine. Measured against the
routes as they stood, two attacks wrote into real status documents —

- a plain `<form>` on any site, auto-submitted at the port, **closed a project
  and emptied its next step**. A form goes cross-origin without a preflight, so
  the browser really delivered it; CORS only hid the answer, which is no
  consolation once the write has happened;
- a domain resolving to `127.0.0.1` (DNS rebinding) was same-origin as far as
  the browser was concerned, and **read the page** as well.

Two checks now stand in front of that, one aimed at each:

- **`Host` is checked on every request**, reads included — the page lists every
  project on the machine by name. Loopback names always pass; any other name has
  to be declared in **`allowed_hosts`** (also `FRONTSTEP_ALLOWED_HOSTS`, comma
  separated, for containers). The refusal names the key that fixes it.
- **Every write carries a token** rendered into the page it came from, in the
  `X-Frontstep-Token` header. A custom header forces a preflight that a route
  answering no CORS header fails, and the value proves the caller was served
  this page. It is generated per process and **kept in memory** — nothing on
  disk, no migration for an existing install, and a restart invalidates every
  page still open. A tab that outlives a restart is told to reload and **keeps
  what was typed in it**.

Not defended, deliberately: a program running as you. It can read the files
directly, so a token it could not steal would protect nothing.

## [0.1.0]

First public release.

### The shape of it

- **One page, derived from files.** A `CURRENT_STATUS.md` per project, read on
  every request. No database and no form to keep the dashboard alive; the page
  reloads by itself when one of those files changes.
- **Three sections** — open, paused, closed — and a **silence line** showing
  where recent work gathers and how long the quiet tail has grown, on a
  logarithmic axis and for open projects only.
- **Any number of roots**, declared in a TOML file with their own label and
  tags. Nothing about anybody's folders is written in the code.
- **Bilingual documents.** Field names and status values are read in English and
  Italian, and **writing follows the document**: a file that says
  `**Stato:** attivo` stays that way, down to the exact field name it uses.
  Nothing is ever migrated.
- **Tags, at two levels.** A root carries base tags; a project's document adds
  its own, and can drop an inherited one by writing it with a minus (`-work`).
- **The agent skill**, which is the engine and not an accessory:
  `frontstep skill --install claude|agents` gives your coding agent the
  convention, so the status documents are kept up to date as part of its normal
  work.

### Writing

Frontstep writes in three places, each one a named line of one header, each one
a button: **Close/Pause** (the status line and its date), the **pencil** next to
*Next step*, and **New project**. All three are atomic, keep the file's owner
and permissions, and keep the document's language.

- `writable = false` in the configuration turns the dashboard read-only: the
  commands leave the page **and** the routes behind them answer `403`.
- A command only appears where there is a line to rewrite — no `Status` line, no
  Close button; no `Next step` line, no pencil.

### Coming from a folder of documents already written

Nothing has to be migrated, but two fields are read differently than their names
suggest:

- **`Domain:` is read as a tag.** `Domain: ACME` becomes the tag `acme`, and the
  historical values (`PERSONALE`, `privato`, `lavoro`…) map onto `personal` and
  `work` so that one spelling does not become two filters.
- **`Prod:` becomes the tag `prod`**, and its value stays as the badge's note.
  A field filled in with a negation (`no`, `not yet`, `nessuno`) counts as
  absent.

### Accessibility

- Colour contrast is **computed from the stylesheet's own tokens** rather than
  judged by eye: text pairs at 4.5:1, marks at 3:1, in both themes.
- Layout **measured** at 375, 390 and 768 px: no horizontal scrolling, and
  targets at 24×24 or more. The ticks of the silence line are the documented
  exception — their position is the information, so WCAG 2.5.8's *Essential*
  exception applies; they stay reachable by keyboard, by scrolling and by search.

### Notes

- Frontstep is a **local, single-user** application: no authentication, no
  multi-user, no database. It binds to `127.0.0.1` for that reason, and says so
  out loud when told to bind anywhere else.
- The **Terminal** button on a card needs a protocol handler you install
  yourself (see `contrib/`); when it is not there, the page says so rather than
  doing nothing. **Editor** and **Path** need nothing installed.
