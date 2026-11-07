// Glossary and taxon previews (§12.2). Progressive enhancement: without JavaScript a
// marked term is a link to its glossary entry and a taxon name a link to its page.
//  * a glossary term (a.gl): hover, focus or tap shows its definition; a term inside a
//    definition opens that definition in the same popover, with a way back;
//  * a taxon name with a page (a.taxon-link): hover or focus shows a preview (on touch
//    screens a tap opens the page, as before);
//  * the glossary page: search box and category chips.
(function () {
  "use strict";

  // ------------------------------------------------------------ glossary page
  var q = document.getElementById("gl-q");
  if (q) {
    var chips = document.querySelector(".gl-chips"), cat = "";
    q.hidden = false; chips.hidden = false;
    var filter = function () {
      var v = q.value.trim().toLowerCase();
      document.querySelectorAll(".gl-entry").forEach(function (e) {
        e.hidden = !((!cat || e.dataset.cat === cat) && (!v || e.dataset.q.indexOf(v) >= 0));
      });
      document.querySelectorAll(".gl-letter").forEach(function (s) {
        s.hidden = !s.querySelector(".gl-entry:not([hidden])");
      });
    };
    q.addEventListener("input", filter);
    chips.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      chips.querySelectorAll("button").forEach(function (x) { x.classList.toggle("is-on", x === b); });
      cat = b.dataset.cat; filter();
    });
  }

  // ---------------------------------------------------------- popovers (pages)
  var node = document.getElementById("page-data");
  if (!node) return;
  var data = JSON.parse(node.textContent), L = data.labels;
  var touch = window.matchMedia && matchMedia("(hover: none)").matches;
  var pop = document.createElement("div");
  pop.className = "gl-pop"; pop.hidden = true; pop.setAttribute("role", "dialog");
  document.body.appendChild(pop);
  var anchor = null, trail = [];

  function el(tag, cls, text) {
    var e = document.createElement(tag); if (cls) e.className = cls;
    if (text) e.textContent = text; return e;
  }
  function place(a) {
    var r = a.getBoundingClientRect(), w = document.documentElement.clientWidth;
    pop.hidden = false;
    pop.style.left = Math.max(8, Math.min(r.left + window.scrollX, window.scrollX + w - pop.offsetWidth - 8)) + "px";
    pop.style.top = (r.bottom + window.scrollY + 6) + "px";
  }
  function term(key, written) {
    var t = data.glossary[key]; if (!t) return;
    pop.replaceChildren();
    if (trail.length) {
      var back = el("button", "gl-pop__back", "← " + L.gl_back);
      back.type = "button";
      back.addEventListener("click", function () { var prev = trail.pop(); term(prev.key, prev.written); });
      pop.appendChild(back);
    }
    var head = el("p", "gl-pop__term", written || t.term);
    if (written && written.toLowerCase() !== t.term.toLowerCase()) {
      head.appendChild(el("span", "gl-pop__also", " · " + L.gl_also + " " + t.term));
    }
    pop.appendChild(head);
    var def = el("p", "gl-pop__def"); def.innerHTML = t.html; pop.appendChild(def);
    var foot = el("p", "gl-pop__foot");
    var src = el("a", null, "Wikipedia · " + t.title); src.href = t.url; src.target = "_blank"; src.rel = "noopener";
    var see = el("a", null, L.gl_see + " →"); see.href = (anchor && anchor.getAttribute("href").split("#")[0] || "") + "#" + key;
    foot.append(L.gl_source + ": ", src, " · ", see);
    pop.appendChild(foot);
    pop.dataset.key = key;
    if (anchor) place(anchor);
  }
  function preview(a) {
    var key = (a.getAttribute("href").match(/([^/]+)\.html$/) || [])[1];
    var p = key && data.previews[key]; if (!p) return false;
    pop.replaceChildren(); trail = [];
    var card = el("div", "tx-pop");
    if (p.img) {
      var img = el("img", p.silhouette ? "tx-pop__img is-sil" : "tx-pop__img");
      img.src = p.img; img.alt = ""; img.loading = "lazy"; card.appendChild(img);
    }
    var body = el("div");
    var name = el("p", "tx-pop__name"); name.appendChild(el("em", null, p.name)); body.appendChild(name);
    if (p.meta) body.appendChild(el("p", "tx-pop__meta", p.meta));
    card.appendChild(body); pop.appendChild(card);
    pop.dataset.key = "";
    anchor = a; place(a);
    return true;
  }
  function open(a) { anchor = a; trail = []; term(a.dataset.gl, a.textContent); }
  function close() { pop.hidden = true; trail = []; }

  // Taxon links keep their link; their title would cover the preview.
  document.querySelectorAll("a.taxon-link[title]").forEach(function (a) {
    a.setAttribute("aria-label", a.title); a.removeAttribute("title");
  });

  var hideTimer;
  function keep() { clearTimeout(hideTimer); }
  function later() { clearTimeout(hideTimer); hideTimer = setTimeout(close, 250); }
  document.addEventListener("mouseover", function (e) {
    if (touch) return;
    var g = e.target.closest("a.gl"), tx = e.target.closest("a.taxon-link");
    if (e.target.closest(".gl-pop")) { keep(); return; }
    if (g && !g.closest(".gl-pop")) { keep(); open(g); }
    else if (tx && !tx.closest(".gl-pop")) { keep(); preview(tx); }
  });
  document.addEventListener("mouseout", function (e) {
    if (touch) return;
    if (e.target.closest("a.gl, a.taxon-link, .gl-pop")) later();
  });
  document.addEventListener("focusin", function (e) {
    var g = e.target.closest("a.gl"), tx = e.target.closest("a.taxon-link");
    if (g && !g.closest(".gl-pop")) open(g);
    else if (tx && !tx.closest(".gl-pop")) preview(tx);
  });
  document.addEventListener("click", function (e) {
    var inside = e.target.closest(".gl-pop");
    var g = e.target.closest("a.gl");
    if (inside && g) {  // a term inside a definition: open it here, with a way back
      e.preventDefault();
      trail.push({ key: pop.dataset.key, written: pop.querySelector(".gl-pop__term").firstChild.textContent });
      term(g.dataset.gl, g.textContent);
      return;
    }
    if (g && touch && (pop.hidden || pop.dataset.key !== g.dataset.gl)) { e.preventDefault(); open(g); return; }
    if (!inside && !g) close();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
})();
