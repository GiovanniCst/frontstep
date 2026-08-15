# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
"""Frontstep — the aggregated view of every project's status document.

One page, no database: the filesystem is read on every request. The dashboard
is DERIVED from the status documents and is never updated by hand.

The app is built by a FACTORY around a configuration. That is not ceremony: the
three routes that write into somebody else's files have to answer `403` when the
configuration says `writable = false`, and a route whose behaviour depends on a
configuration read at import time cannot be tested at all.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets
import sys
from pathlib import Path

import mistune
from flask import Flask, render_template, request
from markupsafe import Markup, escape

from . import config as C
from . import core as F
from . import i18n as T
from . import launch as L


def markdown_inline(text: str) -> Markup:
    """Only `code`, **bold** and the text of links: headers are markdown, and
    showing the backticks as text makes them unreadable. No library, no other
    markup — escaping happens FIRST, so the content of a file cannot inject
    HTML.
    """
    safe = str(escape(text or ""))
    # [text](url) → text. The destination is dropped on purpose: nothing is
    # navigated from here, and the raw syntax on screen is just noise.
    safe = re.sub(r"\[([^\]]+)\]\([^)\s]*\)", r"\1", safe)
    safe = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", safe)
    return Markup(safe)


# The whole document, when a card is opened. `escape=True` keeps the raw HTML
# of the file out: same choice as the `md` filter above, taken once in the
# renderer instead of line by line.
_document_md = mistune.create_markdown(
    escape=True,
    plugins=["table", "strikethrough", "task_lists", "url"],
)


def markdown_document(text: str) -> Markup:
    return Markup(_document_md(_break_field_lines(text or "")))


def _break_field_lines(text: str) -> str:
    """Markdown joins consecutive lines into one paragraph, and the header —
    several `**Field:** value` lines — would turn into one run-on line. Two
    trailing spaces are Markdown's explicit line break: only those lines are
    touched, so wrapped prose stays one paragraph.
    """
    outside_block = True
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            outside_block = not outside_block
        elif outside_block and F.RE_FIELD_LINE.match(line.strip()) and line.strip():
            line = line.rstrip() + "  "
        lines.append(line)
    return "\n".join(lines)


# What a write route answers when the dashboard is read-only. It is a 403 and
# not a hidden button: the buttons ARE hidden too, but an interface is not a
# barrier — anyone can POST to a URL, and `writable = false` has to mean it.
READ_ONLY = ("Frontstep is running read-only: `writable = false` in "
             "the configuration. Nothing was written.")


# ---- the two checks that stand between a web page and somebody's files ------
#
# Frontstep listens on the loopback interface, and a service on the loopback
# interface is NOT private: it is reachable by every page the browser has open
# and by every other account on the machine. Both were measured against the
# routes before these checks existed, and both wrote:
#
#   * a `<form>` on any site, auto-submitted at `127.0.0.1:9015`, closed a
#     project and emptied its next step. A form may be sent cross-origin
#     without a preflight, so the browser really delivered it; CORS hid the
#     ANSWER from the attacker, which is no consolation when the write already
#     happened;
#   * a name resolving to 127.0.0.1 (DNS rebinding) made that same site
#     same-origin as far as the browser was concerned, and read the page too.
#
# The two checks below are aimed one at each, and neither replaces the other:
#
#   HOST      closes rebinding. The browser sends the name it dialled, and an
#             attacker's name is not in the list however it resolves.
#   TOKEN     closes the cross-origin form, because a custom header forces a
#             preflight that a route answering no CORS header fails. It also
#             asks for proof the caller has READ the page — which is what keeps
#             another account on the same machine from curl-ing the port.
#
# What is deliberately NOT defended: a process running as this user. It can
# read the files directly, so a token it could not steal would protect nothing.
HEADER_TOKEN = "X-Frontstep-Token"

# Always accepted, whatever the configuration says: these are the names that
# mean "this machine" and cannot be made to mean anything else.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _same_secret(sent: str, token: str) -> bool:
    """Constant-time comparison that survives any input.

    `compare_digest` raises TypeError on non-ASCII strings, so `?key=é` was a 500
    with a traceback — from anywhere, without a token.
    """
    try:
        return secrets.compare_digest(sent, token)
    except TypeError:
        return False


def host_allowed(raw_host: str, cfg: C.Config) -> bool:
    """Whether the `Host:` header names this dashboard.

    A request with NO Host is refused: HTTP/1.1 requires it, every browser
    sends it, and defaulting to "allow" on a header the check depends on turns
    the check off for anyone who can omit it.
    """
    host = C.host_only(raw_host)
    if not host:
        return False
    return host in LOOPBACK_HOSTS or host in cfg.allowed_hosts


class Live:
    """The configuration this app is serving RIGHT NOW, and what follows from it.

    It exists because of the first run. Frontstep used to refuse to start
    without a configuration file, which meant the browser saw nothing until the
    command line had been satisfied; now it starts, asks in the page, and
    ADOPTS the answer. Adopting has to work without restarting the process —
    telling somebody who has just filled in a form to go back to a terminal and
    start the program again is not an onboarding, it is a detour.

    So the routes read `live.cfg` rather than closing over a configuration that
    can never change. The derived things live here too, worked out once when a
    configuration arrives: which roots exist by key, and what this machine opens
    a terminal and an editor with.
    """

    def __init__(self, cfg: C.Config | None):
        self.adopt(cfg)

    def adopt(self, cfg: C.Config | None) -> None:
        # An empty configuration rather than None, so that every route can read
        # `live.cfg.something` without asking first. `needs_setup` is the one
        # thing that tells the two states apart.
        self.needs_setup = cfg is None
        self.cfg = cfg or C.Config(roots=[])
        # By key: it is what arrives in the URL, and the only way to know which
        # folder to look a project up in. Two roots can hold two folders with
        # the same name, and "Close" has to write to the right file.
        self.roots = {r.key: r for r in self.cfg.roots}
        # Worked out once, not per request: which programs exist does not change
        # while the process runs, and looking them up on every render would put
        # a handful of PATH searches in front of a page that already reads
        # dozens of files. It also stops the page and the route disagreeing
        # about whether a button should be there.
        self.terminal = L.terminal_for(self.cfg)
        self.editor = L.editor_for(self.cfg)


def _port_of(raw_host: str, fallback: int = 9015) -> int:
    """The port in a `Host:` header. The default when there is none.

    A `Host` with no port means the standard one for the scheme, and Frontstep
    is not served over 80 by anything it set up itself — so the fallback is its
    own default rather than 80.
    """
    text = (raw_host or "").strip()
    tail = text.rsplit("]", 1)[-1] if text.startswith("[") else text
    port = tail.rpartition(":")[2]
    return int(port) if port.isdigit() and 1 <= int(port) <= 65535 else fallback


def _setup_values(data: dict, port: int = 9015) -> tuple[dict, list[dict]]:
    """The setup form, turned into what `config.write_file` wants.

    Raises `ValueError` with something a person can act on. The checks that
    matter are on the FOLDERS: everything else is a number or a flag, but a root
    is a path into somebody's disk, and one that does not exist would give a
    dashboard that is empty for a reason nobody can see.

    The folder is NOT created if it is missing. Onboarding's rule everywhere
    else is that it writes nothing inside anybody's projects, and quietly making
    a directory because a path was mistyped is exactly the surprise that rule
    exists to prevent.
    """
    roots: list[dict] = []
    for entry in (data.get("roots") or []):
        raw = str((entry or {}).get("path", "")).strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ValueError(f"{raw}: an absolute path is needed (~ is fine).")
        if not path.is_dir():
            raise ValueError(f"{path}: there is no folder there.")
        label = str(entry.get("label", "")).strip() or (
            "Home" if path == Path.home() else path.name)
        tags = [t for t in (C.normalize_tag(str(g))
                            for g in (entry.get("tags") or [])) if t]
        roots.append({"path": str(path), "label": label, "tags": tags})

    if not roots:
        raise ValueError("At least one folder is needed: the one your projects "
                         "are in.")

    language = str(data.get("language", "en")).strip().lower()
    if language not in ("en", "it"):
        language = "en"
    try:
        stale_days = max(1, min(365, int(data.get("stale_days", 7))))
    except (TypeError, ValueError):
        stale_days = 7

    return ({"language": language, "stale_days": stale_days, "port": port,
             # Not offered on the form, and not an oversight: this page is
             # reached over the loopback interface, and a first run is not the
             # moment to be asked to reason about network exposure.
             "bind": "127.0.0.1",
             "writable": bool(data.get("writable", True))},
            roots)


def app_from_environment() -> Flask:
    """The factory a WSGI server calls — gunicorn in the image, and anything else.

    ⚠️ It exists because `create_app()` with no argument means SETUP, not "go and
    find the configuration": a container invoking it served the onboarding page
    forever, ignoring the config mounted next to it. Worse, that page needs the
    key `serve` prints, and a WSGI server never runs `serve` — so the key existed
    nowhere and the container could not be used at all.

    So: load the configuration if there is one, and if there is not, put the key
    where the only console here can show it.
    """
    try:
        cfg = C.load()
    except C.ConfigMissing:
        cfg = None
    except C.ConfigInvalid as e:
        # Loudly, at start-up, rather than as a 500 on the first request.
        raise SystemExit(f"Frontstep: {e}") from None

    app = create_app(cfg)
    if cfg is None:
        print(f"Frontstep {__version__} — not set up yet. Open this and it will ask:\n"
              f"    http://<this container>/?key={app.config['FRONTSTEP_TOKEN']}\n"
              "  The key decides which folders may be read and written.",
              file=sys.stderr, flush=True)
    return app


def create_app(cfg: C.Config | None = None) -> Flask:
    """The dashboard, around one configuration — or around none yet.

    Passing `None` starts it in SETUP: the page asks where the projects are and
    writes the configuration itself. That is a reversal of what this used to do
    (refuse to start, and name the command that fixes it), and the reasoning
    that produced the old behaviour still holds — a dashboard that comes up
    pointing at some plausible folder looks broken. A page that asks where to
    look is not an empty page, so it does not fall foul of it.
    """
    app = Flask(__name__)
    live = Live(cfg)
    # Generated at startup and kept in MEMORY, never written to the
    # configuration file. Three things follow, and all three are wanted: there
    # is no secret on disk to leak or to back up, a restart invalidates every
    # page still open, and an existing installation needs no migration to get
    # the defence. The page picks it up from a `<meta>` when it is rendered,
    # which is exactly the proof being asked for.
    token = secrets.token_urlsafe(32)
    app.config["FRONTSTEP_TOKEN"] = token
    # When the code is bind-mounted, `gunicorn --reload` only watches .py files:
    # without this Jinja would keep the template it loaded at startup, and an
    # edit to the page would not show until a restart. It costs one stat per
    # render, on a page that reads dozens of files from disk anyway.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["FRONTSTEP"] = cfg
    app.add_template_filter(markdown_inline, "md")
    app.add_template_filter(markdown_document, "md_doc")

    @app.context_processor
    def language():
        """`t()` and `lang` in every template, without threading them through
        every render call — and there are five.

        The URL wins over the configuration, like the staleness threshold: a view
        stays shareable, and the switcher in the top bar does not have to write a
        file to be remembered for the next click.
        """
        chosen = T.resolve(request.args.get("lang"), live.cfg.language)
        return {"lang": chosen,
                # The second argument is the CONTEXT, and templates pass it only
                # where one English word needs two Italian ones (see `i18n.t`).
                "t": lambda text, context=None: T.t(text, chosen, context),
                # What a button says it will open. Only the three names that
                # DESCRIBE something are translated: `Terminal` is macOS's
                # application, and running it through the catalogue would rename
                # somebody's program to "Terminale" — the label of the button
                # happens to be that same word.
                "program_name": lambda name: (T.t(name, chosen)
                                              if name in L.DESCRIBED_NAMES else name),
                # One function rather than a rule per language: English and
                # Italian agree that one thing takes the singular, and a
                # language that disagrees would need its own catalogue entry
                # anyway. It is here because "1 giorni fa" is what a page says
                # when nobody writes this.
                "plural": lambda n, one, many: T.t(one if abs(n) == 1 else many,
                                                   chosen),
                "languages": T.LANGUAGES,
                # The whole catalogue for that language, for the strings the
                # SCRIPT writes after a click. All of it rather than the subset
                # the script happens to use today: a list of "which keys the
                # client needs" is a second thing to keep in step, and it would
                # be wrong the first time somebody adds a message in JS. In
                # English it is empty — there, the key IS the text.
                "js_strings": Markup(json.dumps(T.CATALOGUE.get(chosen, {}),
                                                ensure_ascii=False))}

    @app.before_request
    def check_host():
        """Every route, reads included: the name in the browser's address bar
        has to be one this dashboard answers to.

        On the READS too, and not only on the writes, because rebinding is not
        only a way to write — a page that reaches this one reads the name of
        every project on the machine, and that is somebody's client list.

        Plain text rather than JSON: this one can land in front of a person who
        typed the address, and a JSON body is a worse thing to read than a
        sentence saying which key to add.
        """
        if host_allowed(request.headers.get("Host", ""), live.cfg):
            return None
        return (
            f"Frontstep does not answer to the address "
            f"{request.headers.get('Host', '(no Host header)')!r}.\n\n"
            "It always answers on localhost. If you reach it by another name, "
            "add that name to `allowed_hosts` in the configuration file:\n\n"
            '    allowed_hosts = ["the-name-you-typed"]\n',
            403, {"Content-Type": "text/plain; charset=utf-8"})

    def refuse_if_not_from_the_page():
        """`None` when the caller proved it read the page, the refusal if not.

        `reason` is there for the page, not for a person: a token that no longer
        matches means the server was restarted under a tab still open, and the
        page reloads itself instead of showing a failure the reader can do
        nothing about.
        """
        sent = request.headers.get(HEADER_TOKEN, "")
        if _same_secret(sent, token):
            return None
        return ({"error": "This request did not come from the Frontstep page "
                          "open on this machine. Nothing was written.",
                 "reason": "token"}, 403)

    def refuse_if_read_only():
        """`None` when writing is allowed, the refusal to return otherwise."""
        return None if live.cfg.writable else ({"error": READ_ONLY}, 403)

    def refuse_write():
        """Both gates, in the order they are meant to be read: is this caller
        allowed to reach the route at all, and only then may it write?"""
        return refuse_if_not_from_the_page() or refuse_if_read_only()

    @app.route("/")
    def home():
        if live.needs_setup:
            return first_run()

        # The threshold lives in the URL so a view can be shared and survives a
        # refresh.
        try:
            stale_days = max(1, min(365, int(request.args.get("stale_days", live.cfg.stale_days))))
        except (TypeError, ValueError):
            stale_days = live.cfg.stale_days

        everything = F.scan(live.cfg.roots, live.cfg.index_file)
        # The tags that exist, most used first — and their colours resolved
        # against each other, so that two tags do not share one. Frequency order
        # is what decides who keeps the colour their name asks for.
        counted = F.count_tags(everything)
        colors = F.assign_colors([name for name, _ in counted])

        return render_template(
            "index.html",
            sections=F.group_into_sections(everything),
            # The time of the read, not the browser's: it is the moment this
            # data was taken off the disk.
            read_at=dt.datetime.now().strftime("%H:%M:%S"),
            fingerprint=F.fingerprint(live.cfg.roots, live.cfg.index_file),
            # The page filters. A tag carried by EVERY project separates nothing
            # on its own, but combined with the others it stays useful: it is
            # shown all the same.
            tags=counted,
            # One function for the band, the badges and the filter buttons, so
            # the three cannot disagree about what colour a tag is.
            tag_color=lambda tag: colors.get(tag, F.color_index(tag)),
            # What the two buttons on a card can actually do here. When the
            # server can open things they POST; when it cannot — a container, or
            # `launch = false` — Terminal falls back to the `frontstep://`
            # handler and Editor disappears. Named, so the page can say WHAT it
            # will open rather than offering a button that might do nothing.
            terminal=live.terminal,
            editor=live.editor,
            # The roots as declared: the "new project" form offers these, so
            # nobody has to type a path and the choice stays inside what is
            # configured.
            roots=live.cfg.roots,
            # Whether the page shows the commands that write. The routes refuse
            # anyway; this is so a read-only dashboard does not offer buttons
            # that can only fail.
            writable=live.cfg.writable,
            timeline=F.silence_line(everything, stale_days),
            stale_days=stale_days,
            # How many projects exist AT ALL, which is not the same question as
            # how many pass the filters — and the page has to say a different
            # thing for each.
            total=len(everything),
            status_filename=live.cfg.status_filename,
            # The two skill windows. `claude_is_here` is a folder existing, not
            # a guess about what somebody uses: with it, the page offers to
            # write the skill; without it, it says so and hands over a prompt to
            # paste instead — this program does not create another program's
            # configuration directory on a machine that has none.
            claude_here=F.claude_is_here(),
            skill_path=str(F.claude_skill_path()),
            signature=F.signature(),
            # Handed to the page so it can hand it back on every write. Reading
            # it out of the rendered page IS the proof: a cross-origin script
            # cannot read this page, and another account on this machine has
            # not been served it.
            token=token,
        )

    @app.route("/project/<root>/<name>")
    def project(root: str, name: str):
        """The whole status document, read again right now: it is the body of
        the window that opens when a card is clicked. An HTML fragment, not JSON
        — the page pastes it in, without a second template engine in the browser.

        The root is in the URL because the name alone does not identify a
        project: `~/projects/x` and `~/x` are two different ones."""
        known = live.roots.get(root)
        doc = F.document(name, known.folder, known.host) if known else None
        if doc is None:
            return render_template("_document.html", doc=None, name=name), 404
        return render_template("_document.html", doc=doc)

    @app.route("/project/<root>/<name>/status", methods=["POST"])
    def change_status(root: str, name: str):
        """Write the header's status: the "Close" and "Pause" buttons on a card.

        There is no separate "closed" field — the status the dashboard already
        classifies projects by is the one that gets moved.
        """
        if (refused := refuse_write()):
            return refused
        known = live.roots.get(root)
        if known is None:
            return {"error": f"Unknown root: {root}"}, 404
        wanted = (request.get_json(silent=True) or {}).get("status", F.DONE)
        try:
            result = F.set_status(name, known.folder, wanted)
        except F.WriteFailed as e:
            # Not a 400: the header is fine and the disk is not. Saying "no
            # status line" here sent people to check a header that was perfect.
            return {"error": str(e)}, 500
        if result is None:
            return {"error": "No status line to change in this document."}, 400
        return result, 200

    @app.route("/project/<root>/<name>/next-step", methods=["POST"])
    def change_next_step(root: str, name: str):
        """Write the header's `Next step` line, and the date along with it.

        The third write, and the only one that carries free text from the page
        into a file. What protects that file is not a check on the text — there
        is nothing to check, it is a sentence — but where it may land: one named
        line of one header, in a folder that is a direct child of a declared
        root.
        """
        if (refused := refuse_write()):
            return refused
        known = live.roots.get(root)
        if known is None:
            return {"error": f"Unknown root: {root}"}, 404
        text = (request.get_json(silent=True) or {}).get("next_step", "")
        if not isinstance(text, str):
            return {"error": "The next step is a line of text."}, 400
        try:
            result = F.set_next_step(name, known.folder, text)
        except F.WriteFailed as e:
            return {"error": str(e)}, 500
        if result is None:
            return {"error": "No `Next step` line to write in this document."}, 400
        return result, 200

    @app.route("/project/new", methods=["POST"])
    def new_project():
        """Create a project: its folder and its status document.

        The root does NOT arrive as a path: it arrives as a key, looked up among
        the ones declared in the configuration — so the client picks from a list
        rather than writing a path.
        """
        if (refused := refuse_write()):
            return refused
        data = request.get_json(silent=True) or {}
        known = live.roots.get((data.get("root") or "").strip())
        if known is None:
            return {"error": "Unknown root."}, 400

        result = F.create_project(
            name=(data.get("name") or "").strip(),
            root=known,
            description=data.get("description") or "",
            app_name=(data.get("app") or "").strip(),
            language=live.cfg.language,
            # Asked for by a checkbox, and off unless it is ticked: AGENTS.md is
            # read by every agent that opens the folder, not only by the one
            # this dashboard is for.
            with_agents=bool(data.get("agents")),
        )
        if "error" in result:
            return result, 400
        return result, 201

    @app.route("/skill/claude", methods=["POST"])
    def install_skill():
        """Write the agent skill where Claude Code reads its skills from.

        The fifth thing Frontstep writes, and the only one OUTSIDE both its own
        configuration and the projects: it lands in another program's folder.
        Which is why it happens on a click and never on its own, why the page
        prints the exact path first, and why it is refused when the folder is
        not there — a machine without `~/.claude` is a machine that does not run
        Claude Code, and creating that directory would be answering a question
        nobody asked.

        `writable = false` refuses it too. That flag reads as "this dashboard
        does not write", and a reading of it that let one write through would be
        the kind of exception nobody remembers.
        """
        if (refused := refuse_write()):
            return refused
        if not F.claude_is_here():
            return {"error": "No ~/.claude folder on this machine, so there is "
                             "nothing to install into."}, 404
        try:
            target = F.install_claude_skill()
        except OSError as e:
            return {"error": f"Could not write the skill: {e}"}, 500
        return {"file": str(target)}, 201

    @app.route("/project/<root>/<name>/open/<what>", methods=["POST"])
    def open_project(root: str, name: str, what: str):
        """Open a terminal or an editor on this project, ON THE SERVER'S MACHINE
        — which is the machine of whoever is looking, because that is the only
        way this application is meant to be run.

        This is the route that made Frontstep a program that starts programs, so
        it is worth being explicit about what does and does not protect it. The
        gate above — the page token, plus the `Host` check on every request — is
        what keeps a caller out. What keeps THIS route from being a shell is that
        it takes no command: `what` picks between two commands decided by the
        configuration, and the only thing that varies is a path already resolved
        against a declared root. Nothing typed anywhere reaches an argv.
        """
        if (refused := refuse_if_not_from_the_page()):
            return refused
        launcher = {"terminal": live.terminal, "editor": live.editor}.get(what)
        if launcher is None:
            # Either an unknown word in the URL or a command this machine has
            # not got. Both are 404: there is nothing here to open with.
            return {"error": f"Nothing configured to open a {what} with."}, 404

        known = live.roots.get(root)
        doc = F.document(name, known.folder, known.host) if known else None
        if doc is None:
            return {"error": "No such project."}, 404

        # The HOST paths, not the ones this process sees: they are the same
        # except in a container, and in a container this route is off anyway.
        folder = F.host_join(known.host, doc["name"])
        try:
            L.run(launcher, folder, doc["host_path"])
        except L.LaunchFailed as e:
            # A command that is configured but not installed. Worth saying which
            # one, because the answer is to fix the configuration.
            return {"error": str(e)}, 500
        return {"opened": what, "with": launcher.name}, 200

    # ---- the first run ------------------------------------------------------
    #
    # Onboarding used to be `frontstep init`, a list of questions in a terminal,
    # and `serve` would not start until it had been answered. So the browser saw
    # nothing at all until the command line had been dealt with — for an
    # application whose whole interface is a page.
    #
    # This is the same questions, in the page. It is also the FOURTH place
    # Frontstep writes, and by some distance the most dangerous: this file
    # decides `bind`, `writable` and which commands may be run. That is why it
    # is behind the key below and not merely behind the page token — the token
    # proves you were served the page, and here the question is who is allowed
    # to be served it in the first place.

    def first_run():
        """The setup page, if the caller has the key printed in the terminal.

        The key is the same value the page uses for writing, handed over in the
        URL because on a first run there is no page yet to have read it from.
        Whoever can see the terminal started the program; on a machine with more
        than one account, nobody else can — and without this, anybody with a
        local account could point Frontstep at somebody's home folder and turn
        on the commands that run programs.

        Jupyter's answer to the same problem, for the same reason.
        """
        if _same_secret(request.args.get("key", ""), token):
            return render_template("setup.html", token=token,
                                   suggestions=F.suggest_roots(),
                                   claude_here=F.claude_is_here(),
                                   skill_path=str(F.claude_skill_path()),
                                   config_path=str(C.default_path()))
        return render_template("setup.html", token="", suggestions=[],
                               claude_here=False, skill_path="",
                               config_path=str(C.default_path())), 403

    @app.route("/setup", methods=["POST"])
    def setup():
        """Write the configuration and start serving it, without a restart.

        Refused once a configuration exists: this route may only ever create the
        first one. Editing afterwards is done in the file, which is a text file
        meant to be edited — and a route that could rewrite it at any time would
        be a route that could turn `writable` back on, or point the dashboard
        somewhere else, for the rest of the process's life.
        """
        if not live.needs_setup:
            return {"error": "Frontstep is already configured. Edit the file: "
                             f"{live.cfg.path or C.default_path()}"}, 403
        if (refused := refuse_if_not_from_the_page()):
            return refused

        data = request.get_json(silent=True) or {}
        try:
            # The port is not on the form and is not defaulted either: it is
            # read off the address this request arrived at. Somebody who started
            # Frontstep on another port because 9015 was taken would otherwise
            # get a file saying 9015, and find it somewhere else tomorrow.
            settings, roots = _setup_values(data, _port_of(request.headers.get("Host", "")))
        except ValueError as e:
            return {"error": str(e)}, 400

        path = C.default_path()
        try:
            C.write_file(path, settings, roots)
            fresh = C.load(path)
        except (OSError, C.ConfigInvalid, C.ConfigMissing) as e:
            return {"error": f"Could not write the configuration: {e}"}, 500

        # ⚠️ The example project, and it is not a flourish. Without it a first
        # run lands on a dashboard with nothing on it, which is the exact thing
        # this project decided against — "a dashboard that opens empty looks
        # broken". `init` had always created it; this route, which is now the
        # main way in, had been written without it, and a clean Windows install
        # showed what that looks like: "No project matches these filters".
        #
        # Its document is the tutorial, so the first page anybody sees explains
        # the convention with an example of it, in a folder on their own disk.
        F.create_example(fresh.roots[0].folder, language=fresh.language)

        # The skill, when it was asked for and there is somewhere to put it. It
        # is the engine of the whole thing — without it nobody keeps these
        # documents current — so it is offered at the one moment somebody is
        # certainly paying attention. Never when `~/.claude` is missing: the
        # checkbox is not even on the page then.
        skill = None
        if data.get("skill") and F.claude_is_here():
            try:
                skill = str(F.install_claude_skill())
            except OSError:
                # A first run that cannot write the skill is still a first run
                # that worked: the configuration is written, the dashboard comes
                # up, and the button on the page offers it again.
                skill = None

        live.adopt(fresh)
        return {"written": str(path), "roots": len(fresh.roots), "skill": skill}, 201

    @app.route("/fingerprint")
    def fingerprint():
        """Changes if and only if the files the page derives from change.

        The page asks for it every half minute and reloads only when the value
        differs from its own: that way it is always current without interrupting
        reading when there is nothing new — which is almost always.
        """
        return {"fingerprint": F.fingerprint(live.cfg.roots, live.cfg.index_file)}, 200

    @app.route("/health")
    def health():
        """Liveness: does not touch the projects' filesystem.

        It carries the version because that is the most direct way to know what
        is actually running in a container, without going inside it.

        The commit date comes out in ISO and not in the page's format: a machine
        reads this, and a localised date is ambiguous outside its own country.
        """
        signature = F.signature()
        date = signature.pop("commit_date", None)
        return {"status": "ok", "service": "frontstep",
                "writable": live.cfg.writable,
                "commit_date": date.isoformat() if date else "", **signature}, 200

    return app
