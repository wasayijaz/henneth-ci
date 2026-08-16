/* Shell script — shell behaviour that the live app.js does not have.
   Pairs with shell.css. Nothing here touches app.js; it only drives the
   one control the shell adds. Linked from dashboard/index.html after
   app.js, last among the shell scripts. */
(function () {
  /* The collapsed sidebar is display:none, so the button that closed it
     (#sideToggle, which lives inside the pane) is unreachable — ChatGPT solves
     this with a floating glyph, and #sidePeek is ours.

     It delegates to #sideToggle rather than toggling .collapsed itself. app.js
     owns that state: it toggles the class, writes localStorage "sideCollapsed",
     and re-labels the button (app.js:6721-6725). A second writer here would be a
     second source of truth for the same flag — the first time the two drifted,
     the pane and the persisted value would disagree on reload. A programmatic
     .click() fires on a display:none element, so the indirection costs nothing. */
  var peek = document.getElementById("sidePeek");
  var toggle = document.getElementById("sideToggle");
  var shell = document.getElementById("shell");
  if (!peek || !toggle || !shell) return;

  /* a display:none element cannot hold focus — .focus() on one silently drops
     focus to <body>, which is worse than leaving it where it was */
  function visible(el) {
    return !!el && el.getClientRects().length > 0;
  }

  peek.addEventListener("click", function () {
    toggle.click();
    syncPeek();
    /* focus follows the pane so a keyboard user is not left on a button that
       just removed itself from the layout */
    if (visible(toggle)) toggle.focus();
  });

  function syncPeek() {
    peek.setAttribute("aria-expanded", shell.classList.contains("collapsed") ? "false" : "true");
  }

  /* the toggle is the other half of the same pair — collapsing from inside the
     pane has to leave the peek button reporting the new state too */
  toggle.addEventListener("click", function () {
    syncPeek();
    /* app.js registered its handler on this element first, so by the time we run
       the class has already flipped — .collapsed here is the post-toggle state.
       Collapsing hides the pane, and #sideToggle with it, so a keyboard user who
       just pressed it would be left focused on a display:none element and the
       next Tab would restart from the top of the document. Hand focus to the
       stand-in that replaces it. */
    if (shell.classList.contains("collapsed") && document.activeElement === toggle) peek.focus();
  });
  syncPeek();
})();
