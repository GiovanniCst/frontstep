# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Giovanni J. Costantini
"""The interface, in more than one language.

Frontstep has read and written status documents in two languages from the
start — a file that says `**Stato:** attivo` stays that way, down to the field
name. The interface around it spoke only English, and that was incoherent
enough to read as a bug: choosing Italian during setup changed the documents and
left every button, every label and the tutorial itself in English.

**The English string IS the key.** No symbolic identifiers, for two reasons that
both cost real time otherwise: a template stays readable to somebody who does
not have this file open, and a missing translation degrades to English instead of
printing `page.filters.tag_hint` at a user. The price is that editing an English
string means editing it here too, and a test catches the ones that drift.

What is NOT translated, deliberately:

  * the FIELD NAMES of a status document (`Status`, `Stato`). Those are not
    interface, they are the file's own vocabulary, and `core.FIELDS` owns them;
  * the status VALUES written to disk, for the same reason;
  * anything a user typed. Their words are theirs.
"""
from __future__ import annotations

# The languages the interface exists in. Anything else falls back to English —
# which is a real fallback and not an error: an unknown language shows a working
# page in the project's own language.
LANGUAGES = ("en", "it")

IT: dict[str, str] = {
    # ---- the top bar
    "Frontstep — project status": "Frontstep — stato dei progetti",
    "status documents": "documenti di stato",
    "derived, never written by hand": "derivata, mai scritta a mano",
    "New project": "Nuovo progetto",
    "Create a project: its folder and its status document":
        "Crea un progetto: la sua cartella e il suo documento di stato",
    "Reload": "Ricarica",
    "Read the files again now": "Rileggi i file adesso",
    "Theme": "Tema",
    "Light theme": "Tema chiaro",
    "Dark theme": "Tema scuro",
    "Automatic theme": "Tema automatico",
    "Follow the system theme": "Segui il tema di sistema",
    "Language": "Lingua",
    "read-only": "sola lettura",
    "Frontstep is configured read-only: writable = false":
        "Frontstep è in sola lettura: writable = false",

    # ---- the silence line
    "Silence line": "Linea del silenzio",
    "today": "oggi",
    "days ago": "giorni fa",
    "day ago": "giorno fa",
    "silent for": "in silenzio da",
    "days": "giorni",
    "day": "giorno",
    "The commit this page runs from": "Il commit da cui gira questa pagina",
    "One tick per open project — paused and closed ones are not quiet, they are "
    "stopped on purpose. From the most silent on the left to today on the right, "
    "logarithmic. It follows the filters. Click a tick to reach its card.":
        "Una tacca per ogni progetto aperto — sospesi e conclusi non sono in "
        "silenzio, sono fermi per scelta. Dal più silenzioso a sinistra a oggi a "
        "destra, logaritmica. Segue i filtri. Clicca una tacca per andare alla "
        "sua scheda.",

    # ---- the filters
    "Which projects to show": "Quali progetti mostrare",
    "Filter by tag": "Filtra per tag",
    "Quiet for": "Fermo da",
    "Show only projects quiet for at least":
        "Mostra solo i progetti fermi da almeno",
    "all": "tutti",
    "Search the projects": "Cerca fra i progetti",
    "Search name, next step, person…": "Cerca nome, prossimo passo, persona…",
    "No project matches these filters.": "Nessun progetto corrisponde a questi filtri.",
    "Nothing to show yet: no folder inside your roots has a":
        "Ancora niente da mostrare: nessuna cartella dentro le tue radici ha un",
    "in it.": "dentro.",
    "Add one by hand, press": "Aggiungine uno a mano, premi",
    "above, or run": "qui sopra, oppure lancia",
    "to write a minimal one into folders you pick.":
        "per scriverne uno minimo nelle cartelle che scegli.",

    # ---- the sections
    "Open": "Aperti",
    "Paused": "Sospesi",
    "Closed": "Conclusi",
    "Active": "Attivo",
    "Waiting on others": "In attesa di altri",
    "Header to fix": "Header da sistemare",
    "Done": "Concluso",

    # ---- a card
    # "Paused" is two words in Italian and one in English: a SECTION is a group
    # of cards and takes the plural, ONE card takes the singular. The `card|`
    # key wins on a card and the bare one above stays the section title.
    "card|Paused": "Sospeso",
    "Open the status document": "Apri il documento di stato",
    "A project with no folder of its own": "Un progetto senza una cartella propria",
    "Next step": "Prossimo passo",
    "Edit the next step": "Scrivi il prossimo passo",
    "not declared": "non dichiarato",
    "no document": "nessun documento",
    "This folder has no status document": "Questa cartella non ha un documento di stato",
    "no status document in the folder": "nessun documento di stato nella cartella",
    "no header": "niente header",
    "The status line is missing: that is the one declaring who holds the ball, "
    "and without it this project cannot be closed or paused from here":
        "Manca la riga dello stato: è quella che dichiara di chi è la palla, e "
        "senza di lei questo progetto non si può chiudere né sospendere da qui",
    "header behind": "header indietro",
    "The file was touched after the date its header declares":
        "Il file è stato toccato dopo la data che il suo header dichiara",
    "The canonical name is CURRENT_STATUS.md": "Il nome canonico è CURRENT_STATUS.md",
    "Description": "Descrizione",
    "field, and no prose in the document to derive one from.":
        "e nel documento non c'è prosa da cui ricavarne una.",
    "Last change declared": "Ultima modifica dichiarata",
    "not declared, using the file date": "non dichiarata, uso la data del file",
    # The day suffix on a card: `12d` in English, `12g` in Italian. One letter,
    # and leaving it English would be the only English word left on the card.
    "d": "g",
    "Taken from the text of the document: the Description field is missing.":
        "Presa dal testo del documento: manca il campo Descrizione.",
    "Taken from the index line: this project has no status document.":
        "Presa dalla riga dell'indice: questo progetto non ha un documento di stato.",
    # ⚠️ "Nessun campo", not "Nessun": its companion key below translates to
    # "e nel documento non c'è prosa…" and drops the word "field", so the noun
    # has to travel with this half or it disappears from the sentence.
    "No": "Nessun campo",
    "Index only": "Solo indice",
    "Write the next step in the header of": "Scrivi il prossimo passo nell'header di",
    "Writes status active in the header of": "Scrive lo stato «attivo» nell'header di",
    "Writes status done in the header of": "Scrive lo stato «concluso» nell'header di",
    "Writes status paused in the header of": "Scrive lo stato «sospeso» nell'header di",
    "no date declared": "nessuna data dichiarata",
    # Lower case, to match "no header" → "niente header".
    "no": "niente",
    "Open a terminal in": "Apri un terminale in",
    # "con" and not "in": the name that follows is a translated phrase, and
    # Italian would need the preposition to agree with its article — "in il
    # programma…" is what came out. "con" takes every name that can follow it,
    # a described one or a program's own.
    "Open the folder with": "Apri la cartella con",
    # Which of the two a card says depends on what the editor is handed.
    "Open the document with": "Apri il documento con",
    # What the button will open, when there is no program to name — the whole
    # point of asking the system for its own. `launch.DESCRIBED_NAMES` is the
    # list, and only those go through the catalogue: a program keeps its name.
    "the default Windows terminal": "il terminale predefinito di Windows",
    "the program Windows opens .md with": "il programma che Windows usa per i .md",
    "the default text editor": "l'editor di testo predefinito",
    "Copy": "Copia",
    "Terminal": "Terminale",
    "Editor": "Editor",
    "Path": "Percorso",
    "Repo": "Repo",
    "Close": "Chiudi",
    "Pause": "Sospendi",
    "Reopen": "Riapri",
    "Resume": "Riprendi",
    "Sure?": "Sicuro?",
    "Writing": "Scrivo",
    "Did not work": "Non ha funzionato",
    "Save": "Salva",
    "Cancel": "Annulla",
    "Copied": "Copiato",
    "Opening": "Apro",
    "file": "file",
    "Writes this line and today's date into the document":
        "Scrive questa riga e la data di oggi nel documento",

    # ---- the document window
    "The project's status document": "Il documento di stato del progetto",
    "lines": "righe",
    "file changed on": "file modificato il",
    "at": "alle",
    "This project has no status document to show: it only appears in the index.":
        "Questo progetto non ha un documento di stato da mostrare: compare solo "
        "nell'indice.",
    "Close (Esc)": "Chiudi (Esc)",
    "Reading": "Leggo",
    "last read": "ultima lettura",
    "When this page read the files. It reloads by itself as soon as a status "
    "document changes.":
        "Quando questa pagina ha letto i file. Si ricarica da sola appena un "
        "documento di stato cambia.",

    # ---- the new project window
    "Where it goes": "Dove va",
    "Folder name": "Nome della cartella",
    "Letters, digits, dot, dash, underscore. It becomes a folder under the root "
    "you picked.":
        "Lettere, cifre, punto, trattino, underscore. Diventa una cartella dentro "
        "la radice che hai scelto.",
    "App name": "Nome dell'app",
    "What the product is called, not the folder. It shows up on the card's band.":
        "Come si chiama il prodotto, non la cartella. Finisce nella fascia della "
        "scheda.",
    "What it does and what it works on": "Cosa fa e su cosa",
    "— what the project is, not how far along it is":
        "— cos'è il progetto, non a che punto è",
    "Create the project": "Crea il progetto",

    # ---- the two skill windows
    "Skill: Claude": "Skill: Claude",
    "Skill: other agents": "Skill: altri agent",
    "Teach Claude Code to keep these documents up to date":
        "Insegna a Claude Code a tenere aggiornati questi documenti",
    "Teach any other agent to keep these documents up to date":
        "Insegna a qualunque altro agent a tenere aggiornati questi documenti",
    "One file, where Claude Code reads its skills from. From then on it keeps "
    "each project's status document up to date as part of its work — you do not "
    "have to ask.":
        "Un file solo, dove Claude Code legge le sue skill. Da lì in poi tiene "
        "aggiornato il documento di stato di ogni progetto mentre lavora, senza "
        "che tu debba chiederglielo.",
    "Install the skill": "Installa la skill",
    "Install the agent skill for Claude Code, which is what keeps these "
    "documents up to date":
        "Installa la skill per Claude Code, che è quella che tiene aggiornati "
        "questi documenti",
    "An agent reads its skills when it starts: restart it afterwards.":
        "Un agent legge le sue skill quando parte: riavvialo dopo.",
    "No ~/.claude folder on this machine, so there is nothing to install into — "
    "this may simply not be the machine you run Claude on. Paste this into a "
    "Claude session instead:":
        "Su questa macchina non c'è la cartella ~/.claude, quindi non c'è dove "
        "installare — può semplicemente non essere la macchina su cui usi "
        "Claude. Incolla questo in una sessione di Claude:",
    "Every other agent reads AGENTS.md, and that file lives inside a project "
    "rather than in one place on this machine. So there is no single install: "
    "it goes in one project at a time.":
        "Ogni altro agent legge AGENTS.md, e quel file sta dentro un progetto "
        "invece che in un posto solo sulla macchina. Quindi non c'è "
        "un'installazione unica: si fa un progetto per volta.",
    "When you create a project with New project, tick «Add AGENTS.md» and it is "
    "written for you.":
        "Quando crei un progetto con Nuovo progetto, spunta «Aggiungi "
        "AGENTS.md» e viene scritto da sé.",
    "For a project that already exists, paste this into a session of your "
    "agent, in that project's folder:":
        "Per un progetto che esiste già, incolla questo in una sessione del tuo "
        "agent, nella cartella di quel progetto:",
    "Add AGENTS.md, so your agent keeps this document up to date":
        "Aggiungi AGENTS.md, così il tuo agent tiene aggiornato questo documento",
    "The instructions go in a marked section; anything else in the file is left alone.":
        "Le istruzioni vanno in una sezione delimitata; il resto del file non si tocca.",
    "Did not work: no answer from the server.":
        "Non ha funzionato: nessuna risposta dal server.",

    # ---- notes the page shows
    "Frontstep has been restarted since this page was opened, so nothing was "
    "written.": "Frontstep è stato riavviato da quando questa pagina è stata "
                "aperta, quindi non è stato scritto niente.",
    "Reload the page": "Ricarica la pagina",
    "and try again — copy what you typed first, it is still here.":
        "e riprova — prima copia quello che hai scritto, è ancora qui.",
    "Nothing opened.": "Non si è aperto niente.",
    "It did not open.": "Non si è aperto.",
    "The frontstep:// handler is probably not installed on this machine — it is "
    "in contrib/ of the Frontstep repository.":
        "L'handler frontstep:// probabilmente non è installato su questa "
        "macchina — sta in contrib/ del repository di Frontstep.",
    "Did not work.": "Non ha funzionato.",

    # ---- the setup page
    "Frontstep — set up": "Frontstep — configurazione",
    "One page derived from your projects' status documents. Tell it where they "
    "are — you can change any of this later in":
        "Una pagina sola, derivata dai documenti di stato dei tuoi progetti. "
        "Dille dove sono — puoi cambiare tutto più avanti in",
    "Where your projects are": "Dove stanno i tuoi progetti",
    "Found on this machine. The count is how many folders inside already have a "
    "status document — zero everywhere is normal on a first run, since nobody "
    "has written one yet.":
        "Trovate su questa macchina. Il numero dice quante cartelle dentro hanno "
        "già un documento di stato — zero dappertutto è normale al primo avvio, "
        "visto che nessuno ne ha ancora scritto uno.",
    "project": "progetto",
    "projects": "progetti",
    "Another folder": "Un'altra cartella",
    "How it should behave": "Come deve comportarsi",
    "Language for new status documents and for this page":
        "Lingua dei nuovi documenti di stato e di questa pagina",
    "A project is quiet after": "Un progetto è fermo dopo",
    "days": "giorni",
    "May Frontstep write to your status documents? It only ever rewrites named "
    "lines of the header — the status, the date and the next step — and never "
    "anything else in the file.":
        "Frontstep può scrivere nei tuoi documenti di stato? Riscrive soltanto "
        "righe nominate dell'header — lo stato, la data e il prossimo passo — e "
        "mai nient'altro nel file.",
    "Start": "Comincia",
    "That did not work.": "Non ha funzionato.",
    "No answer from Frontstep.": "Nessuna risposta da Frontstep.",
    "Frontstep is waiting to be set up, and the address to do it at is in the "
    "terminal you started it from — it has a key on the end.":
        "Frontstep aspetta di essere configurato, e l'indirizzo per farlo è nel "
        "terminale da cui l'hai avviato — ha una chiave in fondo.",
    "Go and copy that line.": "Vai a copiare quella riga.",
    "The key is there because this page decides which folders Frontstep may read "
    "and write, and on a machine with more than one account, being able to reach "
    "a port is not the same as being the person sitting at it.":
        "La chiave c'è perché questa pagina decide quali cartelle Frontstep può "
        "leggere e scrivere, e su una macchina con più di un account raggiungere "
        "una porta non è la stessa cosa che essere la persona seduta davanti.",
}

CATALOGUE = {"it": IT}


def t(text: str, language: str = "en", context: str | None = None) -> str:
    """The interface string, in `language`. The English one when there is none.

    Falling back to English rather than raising is deliberate: a missing
    translation should cost a reader one sentence in another language, not a
    broken page — and it must not be able to take the dashboard down at render
    time over a piece of text.

    `context` is gettext's `msgctxt` with a plainer separator, and it exists for
    the price this file pays for using the English string as the key: one
    English word can need two Italian ones. "Paused" is a section — a group of
    cards, plural in Italian — and also the state of a single card, singular.
    The prefixed key is tried first and the bare one catches everything else, so
    a context nobody has translated degrades to the normal translation rather
    than all the way to English.
    """
    if language == "en":
        return text
    catalogue = CATALOGUE.get(language, {})
    if context:
        translated = catalogue.get(f"{context}|{text}")
        if translated is not None:
            return translated
    return catalogue.get(text, text)


def resolve(asked: str | None, configured: str) -> str:
    """Which language this request is in.

    The URL wins over the configuration, the same way the staleness threshold
    does: a view stays shareable and survives a refresh, and switching language
    does not have to write a file to be remembered for the next click.
    """
    for candidate in ((asked or "").strip().lower(), (configured or "").strip().lower()):
        if candidate in LANGUAGES:
            return candidate
    return "en"
