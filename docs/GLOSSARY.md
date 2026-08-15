# Glossary

Frontstep was written in Italian and translated to English. This table is the
mapping that was used, kept because the domain words were chosen carefully and
a contributor should be able to see what each one replaced.

## Domain

| Italian | English | Note |
|---|---|---|
| fronte | project | an open front of work: a folder with a status document |
| radice | root | a folder that is scanned for projects |
| documento di stato | status document | the `CURRENT_STATUS.md` of a project |
| stato | status | who holds the ball: active, waiting, paused, done |
| sezione / gruppo | section | the three groups on the page: open, paused, closed |
| linea del silenzio | silence line | the axis showing how long each project has been quiet |
| tacca | tick | one project on that axis |
| carta | paper | the card background, which carries the status |
| fascia | band | the coloured strip on top of a card, carrying the primary tag |
| impronta | fingerprint | the hash the page polls to know whether anything changed |
| soglia | threshold | after how many days a project counts as stale |
| firma | signature | the version/commit line in the footer |

## Status values

| Italian | English (canonical) |
|---|---|
| attivo | `active` |
| in-attesa | `waiting` |
| sospeso | `paused` |
| concluso | `done` |
| da-adeguare | `undeclared` — not a status of the work, a diagnosis of the document |

## Header fields

Both spellings are read; the English one is written for new documents unless the
document being edited already uses Italian.

| Italian | English |
|---|---|
| `Stato` | `Status` |
| `Aggiornato` | `Updated` |
| `Prossimo passo` | `Next step` |
| `In attesa di` | `Waiting for` |
| `Descrizione` | `Description` |
| `App` | `App` |
| `Tag` | `Tags` |
| `Prod` | `Prod` |

Also accepted, read-only: `State`, `Last updated`, `Date`, `Next`, `Waiting on`,
`Blocked by`, `About`, `Product`, `Nome app`, `Etichette`, `Labels`, `Domain`,
`Dominio`, `Ambito`, `Production`, `Produzione`, `Deploy`, `Deployed`.
