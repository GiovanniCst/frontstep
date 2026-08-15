/* Frontstep — the first run.
   Its own file, not part of frontstep.js: that one runs against a dashboard
   full of cards and would spend its life checking whether anything it looks for
   exists. Two pages, two scripts, neither carrying the other's assumptions. */
(function () {
  "use strict";

  var form = document.getElementById("setup-form");
  if (!form) return;                       // the no-key page has no form

  var TOKEN = (document.querySelector('meta[name="frontstep-token"]') || {}).content || "";

  // Same catalogue as the rest of the page, same keys: the two must not drift
  // into two translations of one sentence.
  var STRINGS = {};
  try {
    var box = document.getElementById("i18n");
    if (box) STRINGS = JSON.parse(box.textContent);
  } catch (e) { /* a broken catalogue must not take the page down */ }
  function t(text) { return STRINGS[text] || text; }
  var error = document.getElementById("setup-error");

  function chosenRoots() {
    var roots = [];
    document.querySelectorAll('input[name="root"]:checked').forEach(function (box) {
      roots.push({ path: box.value, label: box.dataset.label, tags: [] });
    });
    var extra = document.getElementById("extra-root").value.trim();
    // No label and no tags: the server names it after its folder. Asking for a
    // label here would be a second question about a folder that has a name.
    if (extra) roots.push({ path: extra, label: "", tags: [] });
    return roots;
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var go = form.querySelector(".setup-go");
    error.hidden = true;
    go.disabled = true;
    go.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + t("Writing");

    fetch("setup", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Frontstep-Token": TOKEN },
      body: JSON.stringify({
        roots: chosenRoots(),
        language: document.getElementById("language").value,
        stale_days: parseInt(document.getElementById("stale-days").value, 10),
        writable: document.getElementById("writable").checked,
        // Only on the page when ~/.claude is there; absent means no, which is
        // the same answer as an unticked box.
        skill: !!(document.getElementById("skill") || {}).checked,
      }),
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d }; });
    }).then(function (result) {
      if (!result.ok) {
        error.textContent = result.d.error || t("That did not work.");
        error.hidden = false;
        go.disabled = false;
        go.innerHTML = '<i class="fas fa-check"></i> ' + t("Start");
        return;
      }
      // The server is now serving the configuration it has just written, so the
      // dashboard is one plain reload away — no restart, and no instruction to
      // go back to a terminal, which is the entire point of doing this here.
      window.location.href = "/";
    }).catch(function () {
      error.textContent = t("No answer from Frontstep.");
      error.hidden = false;
      go.disabled = false;
      go.innerHTML = '<i class="fas fa-check"></i> ' + t("Start");
    });
  });
})();
