# The status document convention

This is the specification. Everything else — the agent skill, the `AGENTS.md`
block, the example project — is a face of this document, not a separate source.

A project is a folder containing a file named **`CURRENT_STATUS.md`** (that
exact casing; other casings are read but flagged). The file is ordinary
Markdown. Only its header is parsed; the body belongs to whoever writes it.

## The header

The six lines come right after the `# Title`, in this order:

```markdown
# Project name

**Status:** active | waiting | paused | done
**Updated:** 2026-08-14
**Next step:** one line, imperative: what happens next session
**Waiting for:** a person or an event — empty when the ball is ours
**App:** what the product is called, not the folder
**Description:** what this project is, in one line
```

Two optional lines, written only when they say something:

```markdown
**Tags:** prod, client-acme
**Prod:** name-of-the-service
```

### Status

| Value | Meaning |
|---|---|
| `active` | the work is ours and could restart right now |
| `waiting` | blocked on somebody else — `Waiting for` says who |
| `paused` | stopped by choice, not by an external block |
| `done` | delivered, nothing open on our side |

A missing or unreadable status is not an error: the project is shown as
**undeclared**, which is a diagnosis of the document, not a state of the work.
`undeclared` is never written into a file.

**The status is declared, the staleness is measured.** Nothing in the file ever
says "quiet for N days": that is computed from `Updated`, and the two would
disagree within a week.

A `done` project may keep a `Next step`. Deciding to close something while
knowing what would come next is a legitimate state, not an inconsistency.

### Updated

`YYYY-MM-DD`, the date of the last real work. It beats the file's mtime, which
changes for a typo fix too — but when it is missing the mtime is used as a
fallback, and when the file was touched later than the date declared the card
says so.

### Description

The field that does not age: it says what the project **is**, not how far along
it is. One physical line — a line break inside it truncates the value — 60 to
140 characters, no full stop, in the form *what it does + on what*.

Out: status, dates, progress, who you are waiting for (all of those are other
fields), and also stack, port, host and repository name, which belong in the
body. A technical anchor earns its place only when it **is** the project's
identity, not when it is the infrastructure hosting it.

Where the field is missing, the dashboard derives one from the document's prose
and shows it in a fainter grey. That is a safety net, not the intended place.

### Tags

Free labels, normalised to lowercase with dashes (`Client Acme` → `client-acme`).
They come from two levels and add up:

- the **root** the project sits under gives its tags to everything in it;
- the **document** adds its own.

An inherited tag can be removed by writing it with a minus: `**Tags:** -work,
personal`. That is for the project sitting in the wrong folder — a personal one
among the work ones — and without it inheritance would be a cage.

`**Prod:** <name>` adds the tag `prod` and keeps its value as the badge's note:
that field exists because its value says *where* the thing runs.

## Languages

Field names and status values are read in English and Italian:

| English | Italian |
|---|---|
| `Status:` / `active, waiting, paused, done` | `Stato:` / `attivo, in-attesa, sospeso, concluso` |
| `Updated:` | `Aggiornato:` |
| `Next step:` | `Prossimo passo:` |
| `Waiting for:` | `In attesa di:` |
| `Description:` | `Descrizione:` |
| `Tags:` | `Tag:` |

Also accepted on reading: `State`, `Last updated`, `Date`, `Next`, `Waiting on`,
`Blocked by`, `About`, `Product`, `Etichette`, `Labels`, `Domain`, `Dominio`,
`Ambito`, `Production`, `Produzione`, `Deploy`, `Deployed`.

**Writing follows the document.** A file that says `**Stato:** attivo` stays
Italian after Frontstep changes its status, and keeps the exact field name it
already used — someone who wrote `Last updated` does not find `Updated` there
afterwards. Only a brand new document uses the configured language, because
there is nothing to inherit from.

## What is tolerated

The parser is deliberately forgiving: a hand-written document should never break
anything.

| Case | What happens |
|---|---|
| No header at all | the project still shows, badged as having no header |
| Header without a status line | badged, and the buttons that would rewrite that line do not appear |
| Header without a `Next step` line | the pencil that would write it does not appear either — same rule |
| `current_status.md` / `.MD` | read anyway, the casing is badged on the card |
| Unreadable or missing `Updated` | falls back to the file's mtime |
| `Updated` repeated in the body | the **first** occurrence wins — that is the header |
| `paused 2026-04-23`, `active, to run` | normalised to the status |
| An unrecognised tag value | kept as a tag; nothing is invented |

## Rules for whoever keeps these files

1. `Updated` is the date of the session, not of the file.
2. `Next step` is rewritten at the end of a session.
3. `Waiting for` is emptied as soon as the answer arrives, and the status goes
   back to `active`. A filled `Waiting for` on an `active` project makes the page
   lie.
4. A field that cannot be filled in from facts stays empty. An invented value is
   worse than a blank: someone will act on it.
5. Never write a credential value in this file — the name of an environment
   variable, never its content.
