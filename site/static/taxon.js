// Taxon page (ALCANCE.md §11.1): the level of relatives shown, the contents that mark
// the section being read, and citation numbers that show their source. Without
// JavaScript both levels of relatives are shown and a citation links to its source.
(function () {
  "use strict";

  // Relatives: one level at a time ("Group" / "One level up").
  document.querySelectorAll("[data-kin]").forEach(function (box) {
    var buttons = box.querySelectorAll("[data-kin-level]");
    if (!buttons.length) return;
    box.querySelector(".kt__levels").hidden = false;
    function show(level) {
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.kinLevel === level)); });
      box.querySelectorAll("[data-kin-chart]").forEach(function (c) { c.hidden = c.dataset.kinChart !== level; });
    }
    buttons.forEach(function (b) { b.addEventListener("click", function () { show(b.dataset.kinLevel); }); });
    show(buttons[0].dataset.kinLevel);
  });

  // Contents: mark the section on screen.
  var toc = document.querySelector(".tx-toc");
  if (toc && "IntersectionObserver" in window) {
    var links = toc.querySelectorAll("a[href^='#']");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle("is-on", a.getAttribute("href") === "#" + e.target.id); });
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    document.querySelectorAll(".tx-sec[id]").forEach(function (s) { io.observe(s); });
  }

  // Citations: hover (or tap, on touch screens) shows the source in place.
  var read = document.querySelector(".tx-read");
  if (!read) return;
  var pop = document.createElement("div");
  pop.className = "ref-pop"; pop.hidden = true; pop.setAttribute("role", "note");
  document.body.appendChild(pop);
  var label = document.documentElement.lang === "es" ? "Fuente" : "Source";
  function show(a) {
    var src = document.getElementById("src-" + a.dataset.ref);
    if (!src) return;
    pop.replaceChildren();
    var b = document.createElement("strong"); b.textContent = label + " " + a.dataset.ref + ": ";
    pop.appendChild(b);
    Array.prototype.forEach.call(src.childNodes, function (n) { pop.appendChild(n.cloneNode(true)); });
    var r = a.getBoundingClientRect();
    pop.style.left = Math.max(8, Math.min(r.left + window.scrollX, document.documentElement.clientWidth - 360)) + "px";
    pop.style.top = (r.bottom + window.scrollY + 6) + "px";
    pop.hidden = false;
  }
  pop.addEventListener("mouseleave", function () { pop.hidden = true; });
  var touch = window.matchMedia && matchMedia("(hover: none)").matches;
  read.addEventListener("mouseover", function (e) { var a = e.target.closest("[data-ref]"); if (a) show(a); });
  read.addEventListener("mouseout", function (e) { if (e.target.closest("[data-ref]") && !e.relatedTarget?.closest?.(".ref-pop")) pop.hidden = true; });
  read.addEventListener("focusin", function (e) { var a = e.target.closest("[data-ref]"); if (a) show(a); });
  read.addEventListener("click", function (e) {
    var a = e.target.closest("[data-ref]");
    if (a && touch && pop.hidden) { e.preventDefault(); show(a); }
  });
  document.addEventListener("click", function (e) { if (!e.target.closest("[data-ref]") && !e.target.closest(".ref-pop")) pop.hidden = true; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") pop.hidden = true; });
})();
