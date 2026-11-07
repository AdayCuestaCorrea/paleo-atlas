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
