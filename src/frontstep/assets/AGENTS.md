<!-- frontstep:begin -->
## Project status document

This project carries a `CURRENT_STATUS.md`: a Markdown file whose header is the
only place the project's state is declared. A dashboard derives a page from all
such files across every project; that page is never edited by hand.

**Keep it current as part of the work.** At the end of a session on this
project, update it in the same pass as the code.

```markdown
# Project name

**Status:** active | waiting | paused | done
**Updated:** 2026-08-14
**Next step:** one line, imperative: what happens next session
**Waiting for:** a person or an event — empty when the ball is ours
**App:** what the product is called, not the folder
**Description:** what this project is, in one line
```

Optional, written only when they say something: `**Tags:**` (free labels, they
become filters) and `**Prod:**` (the service name, only when it is deployed).

| Status | When |
|---|---|
| `active` | the work is ours and could restart right now |
| `waiting` | blocked on somebody else — then fill in `Waiting for` |
| `paused` | stopped by choice, not by an external block |
| `done` | delivered, nothing open on our side |

Rules that matter:

- `Updated` is the date of the session, `YYYY-MM-DD`. **The status is declared,
  the staleness is measured**: never write "stalled for N days" — that is
  computed from `Updated`.
- `Next step` gets rewritten at the end of every session.
- `Waiting for` is emptied as soon as the answer arrives, and the status goes
  back to `active`.
- `Description` says what the project IS, not how far along it is: one line,
  60–140 characters, no full stop, *what it does + on what*. It changes only if
  the nature of the project changes.
- A field that cannot be filled in from facts stays empty. An invented value is
  worse than a blank.
- Field names and values are accepted in English or Italian. **Do not translate
  a document already written in one language** — keep writing it in that one.
- Never write a credential value in this file.
<!-- frontstep:end -->
