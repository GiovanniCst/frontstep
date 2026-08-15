# Frontstep example

**Status:** active
**Updated:** {today}
**Next step:** Add a status document to a project you actually have, then delete this folder
**Waiting for:**
**App:** Example
**Description:** The example project Frontstep creates on first run, and the tutorial for its convention
**Tags:** example

> **Le stesse istruzioni sono anche in italiano**: scorri in basso, fino a
> «In italiano».

## You are reading a card

The block of bold fields at the top of this file is the **header**, and it is the
only part Frontstep reads. Everything after it is yours: notes, decisions,
whatever the project needs.

Frontstep made this folder on its first run so the dashboard would not open
empty. **Delete it whenever you like** — the folder and this file, nothing else
depends on them.

## The header, field by field

| Field | What it is for |
|---|---|
| `Status` | `active`, `waiting`, `paused` or `done` — who holds the ball |
| `Updated` | the date of the last real work, `YYYY-MM-DD` |
| `Next step` | one imperative line: what the next session starts with |
| `Waiting for` | a person or an event, when you are blocked on somebody else |
| `App` | what the product is called, not the folder — it shows on the card's band |
| `Description` | what the project IS, in one line — not how far along it is |

Two more, written only when they say something: `Tags:` (free labels, they
become the filters at the top of the page) and `Prod:` (the name of the service,
only when it is deployed and running).

**The status is declared, the staleness is measured.** You never write "quiet
for 12 days": the dashboard computes that from `Updated`. You only declare whose
turn it is.

## Getting your own projects onto the page

A project shows up as soon as its folder contains a `CURRENT_STATUS.md` with
that header. Three ways to get there:

**1. By hand.** Copy the header above into a project of yours and fill it in.

**2. Let your agent do it** — this is what Frontstep is built around. Install
the skill once:

```
frontstep skill --install claude     # Agent Skills, in ~/.claude/skills/
frontstep skill --install agents     # AGENTS.md, read by 20+ tools
frontstep skill --print              # print it instead of installing
```

then hand it this prompt:

> Read the Frontstep skill. Add a `CURRENT_STATUS.md` to every project under
> {root_path}. For each one: take the description from its README if it has
> one, otherwise look at the files and infer what the project is; set `Updated`
> from the most recent change inside the folder, ignoring `.git`, `venv`,
> `node_modules` and `__pycache__`; leave `Next step` empty, since that cannot
> be inferred. Ask me which status to use before declaring one.

From then on the agent keeps those files current as it works, and the dashboard
is right without anyone maintaining it.

**3. `frontstep adopt`** — creates a minimal document in the folders you pick.
It fills in what it can measure (the date, and a description derived from the
README) and leaves the rest empty. Enough to make a project appear, which is
better than not knowing you have it.

## What the page does with all this

- Three sections — **open**, **paused**, **closed** — and the same three as
  filters at the top.
- The **silence line**: one tick per open project, from the most silent on the
  left to today on the right. It answers the question no single document can:
  what has gone quiet without anyone deciding it should.
- **Tags** as filters, combining with AND: `work` + `prod` shows the work
  projects that are in production.
- Clicking a card opens its whole document, read from disk right then.

> **The language of the page and the language of this file are two things.**
> The switcher at the top changes the **interface** — labels, buttons, sections
> — and never touches a document: those are yours, and Frontstep comes back to
> each one in the language it found it in. Which is why this tutorial is here in
> both, and why switching the page will not translate the words below.

---

## In italiano

### Stai leggendo una scheda

Il blocco di campi in grassetto in cima al file è l'**header**, ed è l'unica
parte che Frontstep legge. Tutto quello che viene dopo è tuo: note, decisioni,
quello che serve al progetto.

Questa cartella l'ha creata Frontstep al primo avvio, perché la dashboard non si
aprisse vuota. **Cancellala quando vuoi** — la cartella e questo file, non
dipende nient'altro da loro.

### L'header, campo per campo

| Campo | A cosa serve |
|---|---|
| `Stato` | `attivo`, `in-attesa`, `sospeso` o `concluso` — di chi è la palla |
| `Aggiornato` | la data dell'ultimo lavoro vero, `AAAA-MM-GG` |
| `Prossimo passo` | una riga imperativa: da cosa riparte la prossima sessione |
| `In attesa di` | una persona o un evento, quando sei bloccato su qualcun altro |
| `App` | come si chiama il prodotto, non la cartella — finisce nella fascia della scheda |
| `Descrizione` | cos'È il progetto, in una riga — non a che punto è |

Altri due, da scrivere solo quando dicono qualcosa: `Tag:` (etichette libere,
diventano i filtri in cima alla pagina) e `Prod:` (il nome del servizio, solo
quando è pubblicato e gira).

**Lo stato è dichiarato, il silenzio è misurato.** Non scrivi mai «fermo da 12
giorni»: quello lo calcola la dashboard dal campo `Aggiornato`. Tu dichiari solo
di chi è il turno.

### Come portare i tuoi progetti sulla pagina

Un progetto compare appena la sua cartella contiene un `CURRENT_STATUS.md` con
quell'header. Tre strade:

**1. A mano.** Copia l'header qui sopra in un tuo progetto e compilalo.

**2. Fallo fare al tuo agent** — è la cosa attorno a cui Frontstep è costruito.
Installa la skill una volta sola:

```
frontstep skill --install claude     # Agent Skills, in ~/.claude/skills/
frontstep skill --install agents     # AGENTS.md, letto da 20+ strumenti
frontstep skill --print              # stampala invece di installarla
```

poi passagli questo prompt:

> Leggi la skill Frontstep. Aggiungi un `CURRENT_STATUS.md` a ogni progetto
> dentro {root_path}. Per ciascuno: prendi la descrizione dal README se ce l'ha,
> altrimenti guarda i file e deduci cos'è il progetto; imposta `Aggiornato`
> dalla modifica più recente nella cartella, ignorando `.git`, `venv`,
> `node_modules` e `__pycache__`; lascia `Prossimo passo` vuoto, perché non è
> deducibile. Chiedimi quale stato usare prima di dichiararne uno.

Da lì in poi l'agent tiene quei file aggiornati mentre lavora, e la dashboard è
giusta senza che nessuno la mantenga.

**3. `frontstep adopt`** — crea un documento minimo nelle cartelle che scegli.
Compila quello che può misurare (la data, e una descrizione ricavata dal README)
e lascia vuoto il resto. Abbastanza da far comparire un progetto, che è meglio
che non sapere di averlo.

### Cosa fa la pagina con tutto questo

- Tre sezioni — **aperti**, **sospesi**, **conclusi** — e le stesse tre come
  filtri in cima.
- La **linea del silenzio**: una tacca per ogni progetto aperto, dal più
  silenzioso a sinistra a oggi a destra. Risponde alla domanda che nessun
  documento da solo può porre: cos'è andato in silenzio senza che nessuno lo
  decidesse.
- I **tag** come filtri, che si combinano in AND: `lavoro` + `prod` mostra i
  progetti di lavoro che sono in produzione.
- Cliccando una scheda si apre il suo documento intero, letto dal disco in quel
  momento.

> **La lingua della pagina e la lingua di questo file sono due cose diverse.**
> Lo switcher in alto cambia l'**interfaccia** — etichette, pulsanti, sezioni —
> e non tocca mai un documento: quelli sono tuoi, e Frontstep ci torna sopra
> nella lingua in cui li ha trovati. Per questo il tutorial è qui in entrambe, e
> per questo cambiando lingua alla pagina le parole qui sopra restano dove sono.
