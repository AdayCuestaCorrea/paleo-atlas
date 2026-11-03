// Remember the reader's language. Storage may be unavailable (private mode):
// every access is wrapped so the site keeps working without it.
(function () {
  function getLang() { try { return localStorage.getItem("paleo-lang"); } catch (e) { return null; } }
  function setLang(lang) { try { localStorage.setItem("paleo-lang", lang); } catch (e) { /* ignore */ } }

  document.querySelectorAll("a[data-lang]").forEach(function (link) {
    link.addEventListener("click", function () { setLang(link.getAttribute("data-lang")); });
  });

  // On the root chooser, go straight to the remembered language.
  if (document.body.classList.contains("root") && document.querySelector(".chooser__options")) {
    var lang = getLang();
    var target = lang && document.querySelector('a[data-lang="' + lang + '"]');
    if (target) { window.location.replace(target.href); }
  }
})();

// Kinship tree: dim the genera that did not live in the chosen period (§11.2).
(function () {
  var periods = {};  // English name -> [oldest Ma, youngest Ma], read from the SVG
  document.querySelectorAll("[data-tree]").forEach(function (box) {
    box.addEventListener("click", function (event) {
      var button = event.target.closest("[data-tree-period]");
      if (!button) { return; }
      var key = button.getAttribute("data-tree-period");
      box.querySelectorAll("[data-tree-period]").forEach(function (b) {
        b.classList.toggle("chip--on", b === button);
      });
      var band = key && box.querySelector('.tree__period[data-period="' + key + '"]');
      var range = band && [parseFloat(band.getAttribute("data-old")), parseFloat(band.getAttribute("data-young"))];
      box.querySelectorAll(".tree__leaf").forEach(function (leaf) {
        var from = parseFloat(leaf.getAttribute("data-from"));
        var to = parseFloat(leaf.getAttribute("data-to"));
        var lived = !range || (!isNaN(from) && from > range[1] && to < range[0]);
        leaf.classList.toggle("is-dim", !lived);
      });
    });
  });
})();
