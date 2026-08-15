/* SPDX-License-Identifier: Apache-2.0
   Copyright 2026 Giovanni J. Costantini */
/* Frontstep — client-side filtering, theme, copy path, document window.
   The page arrives complete and the JS only hides cards: the one network call
   is the whole document, fetched when a card is opened. */
(function () {
  "use strict";

  /* ---- the interface, in the language the page was rendered in -------------
     The server renders every string in the markup; these are the ones the
     script writes itself, into innerHTML, after a click. They arrive as a JSON
     block the page carries — the same catalogue, keyed the same way, so a
     string written here and one written in a template cannot drift into two
     different translations.

     Missing key = the English text, which is the key. A translation nobody has
     written yet costs one sentence in another language, not a broken button. */
  var STRINGS = {};
  try {
    var box = document.getElementById("i18n");
    if (box) STRINGS = JSON.parse(box.textContent);
  } catch (e) { /* a broken catalogue must not take the page down */ }

  function t(text) { return STRINGS[text] || text; }

  /* ---- every write carries the proof it came from THIS page ---------------
     A page served on the loopback interface is reachable by every other page
     the browser has open. Before this header existed it was measured: a plain
     `<form>` on any site, auto-submitted at this port, closed a project and
     emptied its next step — a form goes cross-origin without a preflight, so
     the browser really delivered it, and CORS only hid the answer.

     A CUSTOM header is what stops that, and the mechanism is the browser's own:
     it turns the request into one that must be preflighted, and the routes
     answer no CORS header, so the real request is never sent. The value on top
     of that proves the caller has READ this page, which no other account on
     this machine has been served.

     It changes every time the server restarts, so a tab left open across one
     holds a token nobody accepts any more and gets a 403 that says which kind
     it is. The page SAYS SO and does not reload itself: reloading was tried
     first and it throws away the sentence just typed, in front of somebody who
     never learns why the page jumped. The note leaves the text where it is,
     long enough to be copied. */
  var TOKEN = (document.querySelector('meta[name="frontstep-token"]') || {}).content || "";
  var STALE = [
    "fa-sync",
    t("Frontstep has been restarted since this page was opened, so nothing was written.") +
    " " + t("Reload the page") + " " +
    t("and try again — copy what you typed first, it is still here."),
  ];

  function write(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Frontstep-Token": TOKEN },
      body: JSON.stringify(payload),
    }).then(function (r) {
      if (r.status !== 403) return r;
      // Only the stale-token 403 says that. `writable = false` is a 403 too and
      // means something else entirely, so the two must not share a message.
      return r.json().then(function (d) {
        if (d && d.reason === "token") note(STALE[0], STALE[1]);
        return Promise.reject(r);
      }, function () { return Promise.reject(r); });
    });
  }

  /* ---- theme: three preferences, two themes ------------------------------
     "auto" is not a theme, it is "follow the system": it has to be resolved to
     light or dark every time the system changes its mind. The preference
     survives a refresh. The first paint is handled by the inline script in
     <head>; the buttons and the system's second thoughts are handled here. */
  var root = document.documentElement;
  var THEME_KEY = "frontstep-theme";             // "light" | "dark" | "auto"
  var systemLight = window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: light)") : null;
  var themeButtons = Array.prototype.slice.call(document.querySelectorAll("[data-theme]"));

  function preference() {
    var p = null;
    try { p = localStorage.getItem(THEME_KEY); } catch (e) { /* privacy mode */ }
    return p === "light" || p === "dark" ? p : "auto";
  }

  function applyTheme(pref, save) {
    root.setAttribute("data-theme", pref === "auto"
      ? (systemLight && systemLight.matches ? "light" : "dark")
      : pref);
    if (save) { try { localStorage.setItem(THEME_KEY, pref); } catch (e) { /* ignore */ } }
    themeButtons.forEach(function (b) {
      b.setAttribute("aria-checked", b.dataset.theme === pref ? "true" : "false");
    });
  }

  themeButtons.forEach(function (b) {
    b.addEventListener("click", function () { applyTheme(b.dataset.theme, true); });
  });

  if (systemLight) {
    var onSystemChange = function () {
      if (preference() === "auto") applyTheme("auto", false);
    };
    if (systemLight.addEventListener) systemLight.addEventListener("change", onSystemChange);
    else if (systemLight.addListener) systemLight.addListener(onSystemChange);  // Safari < 14
  }

  applyTheme(preference(), false);   // line the buttons up with what <head> applied

  /* ---- filters ------------------------------------------------------------
     Four of them, combining with AND: which SECTIONS to show, which TAGS a
     project must carry, how long it must have been quiet, and the search box.
     The section buttons are named after the sections and switch those on —
     no mapping to keep in mind between what you tick and what disappears.
     "Closed" starts off: it is there, but not underfoot. */
  var search = document.getElementById("search");
  var noneMatch = document.getElementById("none-match");
  var groups = Array.prototype.slice.call(document.querySelectorAll(".group"));
  var sectionButtons = Array.prototype.slice.call(document.querySelectorAll(".section-btn"));
  var tagButtons = Array.prototype.slice.call(document.querySelectorAll(".tag-btn"));
  var thresholdButtons = Array.prototype.slice.call(document.querySelectorAll(".threshold-btn"));
  var line = document.querySelector(".silence");
  var ticks = Array.prototype.slice.call(document.querySelectorAll(".tick"));

  function isOn(buttons, key, field) {
    var b = buttons.filter(function (s) { return s.dataset[field] === key; })[0];
    return !b || b.getAttribute("aria-pressed") === "true";
  }

  /* "Quiet for" really filters: it shows only what has been silent for at least
     N days. Zero = everything. Projects with no date at all (-1) drop out as
     soon as the threshold comes on: "no date" is not "quiet for a short while". */
  function activeThreshold() {
    var b = thresholdButtons.filter(function (s) {
      return s.getAttribute("aria-pressed") === "true";
    })[0];
    return b ? Number(b.dataset.threshold) : 0;
  }

  /* Tags that are on combine with AND: `work` + `prod` shows the work projects
     THAT ARE in production, not their union. None on = everything, which is the
     resting position — a filter needs an obvious way of switching itself off,
     or you stay filtered without noticing. */
  function activeTags() {
    return tagButtons
      .filter(function (b) { return b.getAttribute("aria-pressed") === "true"; })
      .map(function (b) { return b.dataset.tag; });
  }

  function hasAllTags(card, wanted) {
    var own = card.dataset.tags || " ";
    for (var i = 0; i < wanted.length; i++) {
      if (own.indexOf(" " + wanted[i] + " ") === -1) return false;
    }
    return true;
  }

  function apply() {
    var q = (search.value || "").trim().toLowerCase();
    var threshold = activeThreshold();
    var wanted = activeTags();
    var visible = 0;

    groups.forEach(function (g) {
      var show = isOn(sectionButtons, g.dataset.group, "section");
      var alive = 0;
      g.querySelectorAll(".card").forEach(function (c) {
        var days = Number(c.dataset.days);
        var ok = show
          && hasAllTags(c, wanted)
          && (!threshold || days >= threshold)
          && (!q || c.dataset.search.indexOf(q) !== -1);
        c.hidden = !ok;
        if (ok) alive++;
      });
      // A section with no visible cards disappears along with its title, rather
      // than leaving an orphan heading behind.
      g.hidden = alive === 0;
      visible += alive;
    });
    noneMatch.hidden = visible > 0;
    updateSilenceLine();
  }

  /* The line looks at the same cards: a tick is there if its card is visible.
     That way the filters apply to the whole page in one go — sections, tags,
     threshold and search — instead of describing a set nobody is looking at.
     It does not rescale: the axis stays the one of all open projects, otherwise
     every click would move the ticks and two views would not be comparable.
     Paused and closed projects never get a tick: the server leaves them out. */
  function updateSilenceLine() {
    if (!line) return;
    var live = 0;
    ticks.forEach(function (t) {
      var card = document.getElementById("project-" + t.dataset.goto);
      var ok = !!card && !card.hidden;
      t.hidden = !ok;
      if (ok) live++;
    });
    line.hidden = live === 0;
  }

  sectionButtons.concat(tagButtons).forEach(function (b) {
    b.addEventListener("click", function () {
      b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
      remember();
      apply();
    });
  });

  // The thresholds are single-choice: "quiet for at least 7 days" and "at least
  // 30" do not add up, the second is contained in the first.
  thresholdButtons.forEach(function (b) {
    b.addEventListener("click", function () {
      thresholdButtons.forEach(function (a) {
        a.setAttribute("aria-pressed", a === b ? "true" : "false");
      });
      remember();
      apply();
    });
  });

  /* ---- filters survive a reload ------------------------------------------
     The page reloads by itself when a file changes (see the bottom of this
     file): without this, every reload would snap the view back to its defaults
     while you are looking at it. Per tab (sessionStorage), not per browser: a
     new tab starts from the defaults. */
  var FILTERS_KEY = "frontstep-filters";

  function remember() {
    // Sections and tags are remembered in opposite ways, because they start
    // from opposite positions: for sections we record which ones are OFF (they
    // start on), for tags which ones are ON (they start off). Recording them
    // the same way would mean saving the list of every existing tag on every
    // single click.
    var saved = { q: search ? search.value : "", threshold: activeThreshold(),
                  off: [], tags: activeTags() };
    sectionButtons.forEach(function (b) {
      if (b.getAttribute("aria-pressed") === "false") saved.off.push(b.dataset.section);
    });
    try { sessionStorage.setItem(FILTERS_KEY, JSON.stringify(saved)); } catch (e) { /* ignore */ }
  }

  function restore() {
    var raw = null;
    try { raw = sessionStorage.getItem(FILTERS_KEY); } catch (e) { return; }
    if (!raw) return;
    var saved;
    try { saved = JSON.parse(raw); } catch (e) { return; }
    if (!saved || !Array.isArray(saved.off)) return;
    if (search && typeof saved.q === "string") search.value = saved.q;
    if (typeof saved.threshold === "number") {
      thresholdButtons.forEach(function (b) {
        b.setAttribute("aria-pressed",
          Number(b.dataset.threshold) === saved.threshold ? "true" : "false");
      });
    }
    sectionButtons.forEach(function (b) {
      b.setAttribute("aria-pressed",
        saved.off.indexOf(b.dataset.section) === -1 ? "true" : "false");
    });
    // A tag that no longer exists (the last project carrying it was closed)
    // simply does not come back on: its button is not there any more.
    var on = Array.isArray(saved.tags) ? saved.tags : [];
    tagButtons.forEach(function (b) {
      b.setAttribute("aria-pressed", on.indexOf(b.dataset.tag) !== -1 ? "true" : "false");
    });
  }

  if (search) {
    var onSearch = function () { remember(); apply(); };
    search.addEventListener("input", onSearch);
    search.addEventListener("change", onSearch);
    // Esc empties the box: that is the gesture expected of a search field.
    search.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { search.value = ""; onSearch(); }
    });
  }

  /* ---- the silence line leads to the card --------------------------------
     One landing at a time: clicking a second tick before the spotlight fades,
     the old timer would put the new spotlight out half way through. */
  var landing = null;
  ticks.forEach(function (t) {
    t.addEventListener("click", function () {
      var target = document.getElementById("project-" + t.dataset.goto);
      if (!target) return;
      // No need to switch filters back on to reach the card: a tick only exists
      // when its card is visible, so a hidden card is never landed on.
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      // The spotlight: for two seconds the other cards dim. With a hundred
      // cards on the page a lit border alone said "somewhere here", not which.
      var list = document.querySelector(".wrap");
      if (list) list.classList.add("spotlight");
      // The spotlight lights one card only: the previous one goes out at once,
      // otherwise it would stay lit when its timer is cleared just below.
      document.querySelectorAll(".card.flash").forEach(function (c) {
        c.classList.remove("flash");
      });
      target.classList.add("flash");
      clearTimeout(landing);
      landing = setTimeout(function () {
        target.classList.remove("flash");
        if (list) list.classList.remove("spotlight");
      }, 2200);
    });
  });

  /* ---- new project --------------------------------------------------------
     Here we collect and check the little that can be checked here; the
     validation that counts is the server's, this only saves a network
     round-trip on an obvious mistake. */
  var newDialog = document.getElementById("new-project");
  var newForm = document.getElementById("new-form");
  var openNew = document.getElementById("open-new");

  if (openNew && newDialog && newForm) {
    var newError = document.getElementById("new-error");
    var descCount = document.getElementById("desc-count");
    var rootChoices = Array.prototype.slice.call(newDialog.querySelectorAll(".root-choice"));

    openNew.addEventListener("click", function () {
      newForm.reset();
      newError.hidden = true;
      descCount.textContent = "0";
      newDialog.showModal();
      newForm.elements.name.focus();
    });

    rootChoices.forEach(function (b) {
      b.addEventListener("click", function () {
        rootChoices.forEach(function (a) {
          a.classList.toggle("on", a === b);
          a.setAttribute("aria-pressed", a === b ? "true" : "false");
        });
      });
    });

    newForm.elements.description.addEventListener("input", function (e) {
      descCount.textContent = e.target.value.trim().length;
    });

    newForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var chosen = rootChoices.filter(function (b) { return b.classList.contains("on"); })[0];
      var payload = {
        root: chosen ? chosen.dataset.root : "",
        name: newForm.elements.name.value.trim(),
        app: newForm.elements.app.value.trim(),
        description: newForm.elements.description.value.trim(),
        agents: newForm.elements.agents.checked,
      };
      newError.hidden = true;
      write("/project/new", payload).then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, d: d }; });
      }).then(function (result) {
        if (!result.ok) {
          // The error stays INSIDE the window: whoever just filled in three
          // fields should not have to look elsewhere to learn what went wrong.
          newError.textContent = result.d.error || t("Did not work.");
          newError.hidden = false;
          return;
        }
        // A terminal opens on the project that was just created: that is what
        // you do next anyway, and it goes the same way the "Terminal" button on
        // a card goes — the server when it can, the handler when it cannot.
        if (document.body.dataset.terminal) {
          write(address(payload.root, payload.name) + "/open/terminal", {})
            .catch(function () { /* the page is about to reload anyway */ })
            .then(function () { window.location.reload(); });
        } else {
          window.location.href = "frontstep://" + payload.root + "/" + payload.name;
          setTimeout(function () { window.location.reload(); }, 800);
        }
      }).catch(function () {
        newError.textContent = t("Did not work: no answer from the server.");
        newError.hidden = false;
      });
    });
  }

  /* ---- a note at the bottom of the page -----------------------------------
     For the one thing the page cannot say any other way: that a click went
     nowhere. It disappears on its own and can be dismissed. */
  var noteTimer = null;

  // ⚠️ `text` goes in as text, never as markup: one of the callers passes the
  // server's error message, which can carry a folder name off the disk.
  function note(icon, text, strong) {
    var box = document.getElementById("note");
    if (!box) {
      box = document.createElement("div");
      box.id = "note";
      box.className = "note";
      box.setAttribute("role", "status");
      document.body.appendChild(box);
      box.addEventListener("click", function (e) {
        if (e.target.closest("[data-close]")) box.remove();
      });
    }
    box.replaceChildren();
    if (icon) {
      var i = document.createElement("i");
      i.className = "fas " + icon;
      box.append(i, " ");
    }
    box.append(text);
    if (strong) { var b = document.createElement("b"); b.textContent = strong; box.append(" ", b); }
    var dismiss = document.createElement("button");
    dismiss.className = "link";
    dismiss.type = "button";
    dismiss.setAttribute("data-close", "");
    dismiss.setAttribute("aria-label", "Dismiss");
    dismiss.innerHTML = '<i class="fas fa-times"></i>';
    box.append(" ", dismiss);
    clearTimeout(noteTimer);
    noteTimer = setTimeout(function () { box.remove(); }, 12000);
  }

  /* ---- the terminal, and saying so when it does not open -------------------
     A page served over http:// cannot start a program: the "Terminal" button
     goes through a `frontstep://` protocol handler that the user registers
     themselves (see contrib/). When it is NOT registered, a browser does
     nothing at all and says nothing — the click falls into silence, and a
     button that sometimes works and sometimes does nothing is the worst kind.

     There is no way to ask a browser whether a scheme is handled, so the
     evidence used is the one that exists: if a handler runs, a window opens and
     this page loses focus or is hidden. Still focused a second and a half
     later, and most likely nothing happened. The wording says "probably" for
     that reason — it is a hint, not a verdict, and it is still better than the
     silence it replaces. */
  var HANDLER_WAIT_MS = 1500;

  function watchHandler() {
    var left = false;
    var mark = function () { left = true; };
    window.addEventListener("blur", mark, { once: true });
    document.addEventListener("visibilitychange", mark, { once: true });
    window.addEventListener("pagehide", mark, { once: true });
    setTimeout(function () {
      window.removeEventListener("blur", mark);
      document.removeEventListener("visibilitychange", mark);
      window.removeEventListener("pagehide", mark);
      if (left || document.hidden) return;
      note("fa-exclamation-triangle", t("Nothing opened.") + " " +
           t("The frontstep:// handler is probably not installed on this machine — it is in contrib/ of the Frontstep repository."));
    }, HANDLER_WAIT_MS);
  }

  /* ---- copy the path ----------------------------------------------------- */
  // The terminal link does not also open the document: it is an <a>, and the
  // card's handler already ignores clicks on <a> and <button>. This only stops
  // the focus from bouncing back onto the link afterwards.
  // Only the FALLBACK terminal link watches for the handler. When the server
  // opens the terminal itself there is nothing to guess at: it either started
  // the program or said why it could not.
  document.querySelectorAll("a.open-terminal.handler").forEach(function (a) {
    a.addEventListener("click", function () { a.blur(); watchHandler(); });
  });

  /* ---- asking the server to open something --------------------------------
     The browser cannot start a program; the server runs on the same machine and
     can. These are the buttons that ask it to.

     The feedback is short on purpose. A terminal opening is its own evidence —
     a window appears, and the page it came from is no longer the thing being
     looked at — so the button says "Opening" for a moment and goes back to what
     it was. What DOES need saying is a failure, because that one is invisible:
     it goes in the note at the bottom, with the reason the server gave. */
  function opener(button, what) {
    button.addEventListener("click", function (ev) {
      ev.stopPropagation();                     // the card opens the document
      var before = button.innerHTML;
      button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + t("Opening");
      button.disabled = true;
      var restore = function () {
        button.innerHTML = before;
        button.disabled = false;
        button.blur();
      };
      write(address(button.dataset.root, button.dataset.project) + "/open/" + what,
            {})
        .then(function (r) {
          return r.ok ? r.json().then(restore)
                      : r.json().then(function (d) {
                          restore();
                          note("fa-exclamation-triangle",
                               d.error || t("It did not open."));
                        });
        })
        .catch(function () { restore(); });     // write() has said what it was
    });
  }

  document.querySelectorAll("button.open-terminal").forEach(function (b) {
    opener(b, "terminal");
  });
  document.querySelectorAll("button.open-editor").forEach(function (b) {
    opener(b, "editor");
  });

  /* ---- the two skill windows ---------------------------------------------
     Opening them is all the page does; the Claude one also has the single
     button that writes, and it reports what happened in the window rather than
     anywhere else — the path it wrote is the thing worth reading. */
  [["open-skill-claude", "skill-claude"], ["open-skill-agents", "skill-agents"]]
    .forEach(function (pair) {
      var button = document.getElementById(pair[0]);
      var dialog = document.getElementById(pair[1]);
      if (button && dialog) {
        button.addEventListener("click", function () { dialog.showModal(); });
      }
    });

  var installSkill = document.getElementById("do-install-skill");
  if (installSkill) {
    var said = document.getElementById("skill-claude-said");
    installSkill.addEventListener("click", function () {
      installSkill.disabled = true;
      installSkill.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + t("Writing");
      write("skill/claude", {}).then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, d: d }; });
      }).then(function (result) {
        installSkill.hidden = result.ok;
        installSkill.disabled = false;
        installSkill.innerHTML = '<i class="fas fa-download"></i> ' + t("Install the skill");
        said.textContent = result.ok
          ? "✓ " + result.d.file
          : (result.d.error || t("Did not work."));
        said.hidden = false;
      }).catch(function () {
        installSkill.disabled = false;
        installSkill.innerHTML = '<i class="fas fa-download"></i> ' + t("Install the skill");
        said.textContent = t("Did not work: no answer from the server.");
        said.hidden = false;
      });
    });
  }

  document.querySelectorAll(".copy-path").forEach(function (b) {
    b.addEventListener("click", function () {
      var text = b.dataset.path;
      var done = function (ok) {
        var before = b.innerHTML;
        b.classList.toggle("copied", ok);
        b.innerHTML = ok
          ? '<i class="fas fa-check"></i> ' + t("Copied")
          : '<i class="fas fa-times"></i> ' + t("Did not work");
        setTimeout(function () { b.innerHTML = before; b.classList.remove("copied"); }, 1400);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { done(true); },
                                                 function () { done(false); });
      } else {
        // http:// on a LAN is not a secure context: the old way is needed.
        var textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        var ok = false;
        try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
        document.body.removeChild(textarea);
        done(ok);
      }
    });
  });

  /* ---- closing or pausing a project ---------------------------------------
     These write the status in the header of the project's own document: the
     only times this app touches somebody else's file, so they take two clicks.
     The card changes colour at once; it lands in the right section on the next
     reload, because that is where the page re-derives itself from the files.

     A button has two faces, decided by the status the card is in RIGHT NOW: if
     it is already there, the command is the one that brings it back to active.
     The faces live here and not in the template because after a write both have
     to be rewritten: closing a paused project must also switch "Resume" off. */
  // A project's address: the root is part of it, because `~/projects/x` and
  // `~/x` are two different projects and we are writing into someone's file.
  function address(root, name) {
    return "project/" + encodeURIComponent(root) + "/" + encodeURIComponent(name);
  }

  var FACES = {
    done:   { action: ['fa-check-circle', t("Close")], undo: ['fa-undo', t("Reopen")] },
    paused: { action: ['fa-pause-circle', t("Pause")], undo: ['fa-play', t("Resume")] }
  };

  /* One whole sentence per status rather than a stem plus the status word: the
     status would be the canonical value, which is a token and not a word, and a
     phrase assembled from pieces only reads in the language it was written for.
     Keyed by literal here so the orphan test can see all three. */
  var TOWARD = {
    active: t("Writes status active in the header of"),
    done:   t("Writes status done in the header of"),
    paused: t("Writes status paused in the header of")
  };

  function face(b) {
    var status = b.closest(".card").dataset.status;
    var f = FACES[b.dataset.target];
    var alreadyThere = status === b.dataset.target;
    var entry = alreadyThere ? f.undo : f.action;
    b.dataset.toward = alreadyThere ? "active" : b.dataset.target;
    b.innerHTML = '<i class="fas ' + entry[0] + '"></i> ' + entry[1];
    b.title = TOWARD[b.dataset.toward] + " " + b.dataset.file;
    b.hidden = false;
  }

  document.querySelectorAll(".status-btn").forEach(function (b) {
    var armed = false;
    var timer = null;
    face(b);

    function disarm() {
      if (!armed) return;
      armed = false; b.classList.remove("armed"); clearTimeout(timer); face(b);
    }

    b.addEventListener("click", function () {
      if (!armed) {
        armed = true;
        b.classList.add("armed");
        b.innerHTML = '<i class="fas fa-exclamation-circle"></i> ' + t("Sure?");
        timer = setTimeout(disarm, 4000);
        return;
      }
      clearTimeout(timer);
      armed = false;
      b.classList.remove("armed");
      b.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + t("Writing");
      write(address(b.dataset.root, b.dataset.project) + "/status",
            { status: b.dataset.toward })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function (result) {
          var c = b.closest(".card");
          c.dataset.status = result.status;
          // every command on the card, not just the one that was pressed
          c.querySelectorAll(".status-btn").forEach(face);
        })
        .catch(function () {
          b.innerHTML = '<i class="fas fa-times"></i> ' + t("Did not work");
          setTimeout(function () { face(b); }, 2000);
        });
    });

    b.addEventListener("blur", disarm);
  });

  /* ---- writing the next step from the card --------------------------------
     The third and last place this app writes into somebody else's file. It is
     the one line of the header that gets rewritten every single session, so it
     is the one worth being able to write without opening an editor.

     No "Sure?" step here, unlike Close and Pause, and the difference is not
     laziness: those change a file with ONE click on a button that was already
     there, so the second click is what makes the act deliberate. Here you open
     a box, type a sentence and press Save — the deliberate act is the typing.

     After a save the page RELOADS. The card cannot be patched honestly: the
     text is rendered server-side (`code`, **bold**, links), the date on the
     card has just moved and the silence count with it. Re-deriving the page
     from the files is what this app does; doing it now beats showing a card
     that is half fresh and half stale until the next automatic reload. */
  var editing = null;                     // one card at a time

  function closeEditor() {
    if (!editing) return;
    var box = editing;
    editing = null;
    box.form.replaceWith(box.text);
    box.pencil.hidden = false;
  }

  document.querySelectorAll(".next-edit").forEach(function (pencil) {
    pencil.addEventListener("click", function (e) {
      e.stopPropagation();                // not a click on the card
      var card = pencil.closest(".card");
      var text = card.querySelector(".next-text");
      if (!text) return;
      closeEditor();

      var form = document.createElement("form");
      form.className = "next-form";
      form.innerHTML =
        '<textarea rows="2" aria-label="Next step" ' +
        'placeholder="One line, imperative: what happens next session"></textarea>' +
        '<div class="next-form-foot">' +
        '<span class="next-hint">' + t("Writes this line and today's date into the document") + '</span>' +
        '<button type="button" class="link" data-cancel>' + t("Cancel") + '</button>' +
        '<button type="submit" class="link next-save"><i class="fas fa-check"></i> Save</button>' +
        '</div>';

      var area = form.querySelector("textarea");
      area.value = pencil.dataset.value || "";
      pencil.hidden = true;
      text.replaceWith(form);
      editing = { form: form, text: text, pencil: pencil };
      area.focus();
      area.setSelectionRange(area.value.length, area.value.length);

      // The card opens the document on a click; the box inside it is neither an
      // <a> nor a <button>, so without this, typing would open the window.
      form.addEventListener("click", function (ev) { ev.stopPropagation(); });
      form.addEventListener("keydown", function (ev) {
        ev.stopPropagation();
        if (ev.key === "Escape") { ev.preventDefault(); closeEditor(); }
        // Enter saves, Shift+Enter would be a line break — which the field does
        // not keep anyway, since the header is read one line at a time.
        if (ev.key === "Enter" && !ev.shiftKey) {
          ev.preventDefault();
          form.requestSubmit();
        }
      });
      form.querySelector("[data-cancel]").addEventListener("click", closeEditor);

      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var save = form.querySelector(".next-save");
        save.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + t("Writing");
        save.disabled = true;
        write(address(pencil.dataset.root, pencil.dataset.project) + "/next-step",
              { next_step: area.value })
          .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
          .then(function () { location.reload(); })
          .catch(function () {
            save.disabled = false;
            save.innerHTML = '<i class="fas fa-times"></i> ' + t("Did not work");
            setTimeout(function () {
              save.innerHTML = '<i class="fas fa-check"></i> ' + t("Save");
            }, 2000);
          });
      });
    });
  });

  /* ---- the whole document, in a window ------------------------------------
     The card is a summary; this is the reading. It is read from disk on every
     open — no cache: the file changes while the page is open, and that is
     exactly when you go and look at it. */
  var dialog = document.getElementById("doc");
  var body = document.getElementById("docBody");
  // Which read is the good one: an answer arriving after a close, or after
  // another project was opened, must not write into the page.
  var reading = 0;

  function openDocument(root, name) {
    var mine = ++reading;
    // ⚠️ textContent, not innerHTML: `name` is a folder name off the disk, and
    // the template's escaping does not survive a trip through `dataset`.
    body.replaceChildren(Object.assign(document.createElement("p"),
      { className: "doc-loading", textContent: t("Reading") + " " + name + "…" }));
    if (!dialog.open) dialog.showModal();
    body.scrollTop = 0;
    fetch(address(root, name), { headers: { "Accept": "text/html" } })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        if (mine !== reading) return;
        body.innerHTML = html; body.focus();
      })
      .catch(function () {
        if (mine !== reading) return;
        body.innerHTML = '<p class="doc-loading">Could not read the document.</p>';
      });
  }

  if (dialog && body) {
    document.querySelectorAll(".card.openable").forEach(function (c) {
      c.addEventListener("click", function (e) {
        // The commands inside a card stay theirs: copying a path or opening the
        // repository is not "opening the document". Nor is selecting text.
        if (e.target.closest("a, button")) return;
        if (window.getSelection && String(window.getSelection()).length) return;
        openDocument(c.dataset.root, c.dataset.doc);
      });
      c.addEventListener("keydown", function (e) {
        if (e.target !== c) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openDocument(c.dataset.root, c.dataset.doc);
        }
      });
    });

    dialog.addEventListener("click", function (e) {
      // Click on the backdrop: <dialog> delivers it to the dialog itself, not
      // to a child.
      if (e.target === dialog || e.target.closest("[data-close]")) dialog.close();
    });
    // Emptying it on close stops a reopen from showing the previous document
    // for an instant while the new one arrives. `reading` moves on so that an
    // answer still in flight does not fill a window that is already closed.
    dialog.addEventListener("close", function () { reading++; body.innerHTML = ""; });
  }

  /* ---- the page keeps itself up to date -----------------------------------
     Status documents are changed by whoever works on those projects — another
     session, an agent, this very app with its "Close" button — and a dashboard
     that says something false until you press F5 is worth nothing.

     It does not reload on a timer: it asks the server for the FINGERPRINT of
     the files (one stat per project, no reads) and reloads only if it differs
     from the one this page was built with. Almost always nothing has changed,
     and then nothing happens.

     Three courtesies, so that a reload does not land on someone who is reading:
     a background tab (checked as soon as it comes back), an open document
     window, a focused search box. In those cases it waits. */
  var EVERY_MS = 30000;
  var readAt = document.getElementById("read-at");

  if (readAt && window.fetch) {
    var myFingerprint = readAt.dataset.fingerprint;
    var reloadPending = false;

    function busy() {
      return (dialog && dialog.open)
        || (search && document.activeElement === search)
        // Someone is halfway through writing a next step: a reload here would
        // throw away a sentence they had just typed.
        || !!editing;
    }

    function reload() {
      readAt.classList.add("refreshing");
      location.reload();
    }

    function check() {
      if (document.hidden) return;                 // it gets looked at on return
      if (reloadPending) {
        if (!busy()) reload();
        return;
      }
      fetch("fingerprint", { headers: { "Accept": "application/json" } })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function (data) {
          if (!data.fingerprint || data.fingerprint === myFingerprint) return;
          reloadPending = true;
          if (!busy()) reload();
        })
        .catch(function () { /* server down or restarting: try again later */ });
    }

    setInterval(check, EVERY_MS);
    // Coming back to the tab is the moment you want to see fresh data.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) check();
    });
    // Closing the document or leaving the search box: if a reload was waiting,
    // now is when it can happen without interrupting anything.
    if (dialog) dialog.addEventListener("close", function () {
      if (reloadPending) reload();
    });
    if (search) search.addEventListener("blur", function () {
      if (reloadPending && !busy()) reload();
    });
  }

  restore();
  apply();
})();
