---
name: frontstep-status
description: Keep each project's CURRENT_STATUS.md up to date — a six-line header saying what the project is, who holds the ball, and what happens next. Use whenever you start or finish work on a project, create a new one, or are asked what is open and where things stand.
---

# Keeping status documents

Every project folder carries a `CURRENT_STATUS.md`. It is a normal Markdown
document with a fixed header on top, and it is the only place a project's state
is declared. A dashboard (Frontstep) derives a single page from all of them; you
never update that page, you update this file.

**You are the one who keeps it current.** The person you work with should not
have to ask. Update it as part of the work, in the same pass as the code.

## The header

Right after the `# Title` line, six lines, in this order:

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
**Tags:** prod, client-acme      → free labels; they become filters on the page
**Prod:** name-of-the-service    → only when it is deployed and running
```

Italian is accepted for every field name and value (`Stato`, `Aggiornato`,
`Prossimo passo`, `In attesa di`, `Descrizione`, and `attivo | in-attesa |
sospeso | concluso`). **Do not translate a document that is already written in
one language**: keep writing it in the language it uses.

## The four statuses

| Status | When |
|---|---|
| `active` | the work is ours and could restart right now |
| `waiting` | blocked on somebody else — then fill in **Waiting for** |
| `paused` | stopped by choice, not by an external block |
| `done` | delivered, nothing open on our side |

**The status is declared, the staleness is measured.** Never write "stalled for
12 days" anywhere: the dashboard computes that from `Updated`. You only declare
whose turn it is.

A `done` project may keep a `Next step`: deciding to stop while knowing what
would come next is a legitimate state. Do not empty it.

## The rules that matter

1. **`Updated` is the date of this session**, in `YYYY-MM-DD`. Not the date the
   file was touched — the date real work happened.
2. **`Next step` gets rewritten** at the end of a session: one imperative line,
   what the next session starts with.
3. **`Waiting for` is emptied** as soon as the answer arrives, and the status
   goes back to `active`. A filled-in `Waiting for` on an `active` project is a
   contradiction that makes the page lie.
4. **`Description` says what the project IS, not how far along it is.** One
   physical line, 60–140 characters, no full stop at the end, form: *what it
   does + on what*. It is the only field that does not age: rewrite it only when
   the nature of the project changes. Keep out: status, dates, progress, stack,
   port, host, repository name — those are in the other fields or in the body.
5. **A field you cannot fill in from facts stays empty.** An invented value is
   worse than a blank: someone will act on it.
6. **Never write a credential value** in this file. The name of an environment
   variable, never its content.
7. The file name is `CURRENT_STATUS.md`, that exact casing.

## Starting a new project

Create the folder, write the document with the header above, `Status: active`,
`Updated` today, `Next step` empty if there is nothing to say yet, and a real
`Description`. Everything else — what the project is about, decisions taken,
what is open — goes in the body under normal Markdown headings.

## Adding it to projects that do not have one

For each project: read its README (or its main documents) and write the
`Description` from what you find there, not from the folder name. Take `Updated`
from the most recent modification inside the folder, ignoring `.git`, `venv`,
`node_modules` and `__pycache__`. Leave `Next step` empty unless the project's
own documents say what it is — that one cannot be inferred, and inventing it is
worse than leaving it blank. Ask which status to use before declaring one.

## The end-of-session ritual

Before you finish work on a project:

- set `Updated` to today;
- rewrite `Next step` so that the next session knows where to start;
- if you are now blocked on someone, set `Status: waiting` and fill in
  `Waiting for`; if you were and no longer are, empty it and go back to
  `active`;
- check that `Description` is still true (usually it is — leave it alone).
