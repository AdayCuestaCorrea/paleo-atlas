// Paleo Atlas home page (ALCANCE.md §11): the curiosity carousel, the explorer and its
// map. The page is complete without JavaScript (the first state is in the HTML: the
// periods, groups and countries link to their indices); this script turns them into
// filters over explore.json (src/paleo/site/explore.py).
(function () {
  "use strict";

  var NEW = 2, CURIOSITIES = 4, PHOTO = 8, SILHOUETTE = 1;

  // ------------------------------------------------------------ pure functions

  // explore.json -> one object per page.
  function decode(ix) {
    var T = ix.terms;
    return ix.taxa.map(function (r) {
      var img = r[2] == null ? null : T[r[2]], bar = img ? img.indexOf("|") : -1;
      if (bar > 0 && bar < 3) img = ix.images[+img.slice(0, bar)] + img.slice(bar + 1);
      var key = r[8] || r[0].trim().replace(/[^A-Za-z0-9]+/g, "-").toLowerCase();
      return { n: r[0], meta: r[1] == null ? "" : T[r[1]], img: img, flags: r[3], group: r[4],
        periods: r[5], countries: r[6], rank: r[7], u: ix.url[0] + key + ix.url[1] };
    });
  }

  // Counts for every option given the other filters (so dead ends can be dimmed), and
  // the pages that pass all of them. state: {scope, time, group, place}: indices or null.
  function tally(taxa, st, sizes) {
    var out = { time: zeros(sizes.time), group: zeros(sizes.group), place: zeros(sizes.place), found: [] };
    taxa.forEach(function (t) {
      if (st.scope === "new" && !(t.flags & NEW)) return;
      var okTime = st.time == null || (t.periods & (1 << st.time)) !== 0;
      var okGroup = st.group == null || t.group === st.group;
      var okPlace = st.place == null || t.countries.indexOf(st.place) >= 0;
      if (okGroup && okPlace) for (var p = 0; p < sizes.time; p++) if (t.periods & (1 << p)) out.time[p]++;
      if (okTime && okPlace && t.group != null) out.group[t.group]++;
      if (okTime && okGroup) t.countries.forEach(function (c) { out.place[c]++; });
      if (okTime && okGroup && okPlace) out.found.push(t);
    });
    return out;
  }
  function zeros(n) { var a = []; for (var i = 0; i < n; i++) a.push(0); return a; }

  // New taxa newest first; the whole atlas with curiosities first, then photos, then the rest.
  function order(list, scope) {
    var tier = function (t) { return t.flags & CURIOSITIES ? 0 : t.flags & PHOTO ? 1 : 2; };
    return list.slice().sort(scope === "new"
      ? function (a, b) { return (a.rank == null ? 1e9 : a.rank) - (b.rank == null ? 1e9 : b.rank); }
      : function (a, b) { return tier(a) - tier(b) || a.n.localeCompare(b.n); });
  }

  // State <-> URL hash, language neutral: "all&time=cretaceous&group=pterosaurs&place=es".
  function toHash(st, keys) {
    var parts = st.scope === "all" ? ["all"] : [];
    ["time", "group", "place"].forEach(function (k) { if (st[k] != null) parts.push(k + "=" + keys[k][st[k]]); });
    return parts.join("&");
  }
  function fromHash(hash, keys) {
    var st = { scope: "new", time: null, group: null, place: null };
    hash.replace(/^#/, "").split("&").forEach(function (part) {
      var kv = part.split("=");
      if (kv[0] === "all" && kv.length === 1) st.scope = "all";
      else if (keys[kv[0]]) { var i = keys[kv[0]].indexOf(decodeURIComponent(kv[1] || "")); if (i >= 0) st[kv[0]] = i; }
    });
    return st;
  }

  // Map view [x, y, w, h] in SVG units (x = longitude, y = -latitude), always 2:1 and
  // inside the world; w between MIN_W and 360.
  var FULL = [-180, -90, 360, 180], MIN_W = 12;
  function clampView(v) {
    var w = Math.min(360, Math.max(MIN_W, v[2])), h = w / 2;
    return [Math.max(-180, Math.min(180 - w, v[0])), Math.max(-90, Math.min(90 - h, v[1])), w, h];
  }
  function boxView(b) { // [lon W, lat N, lon E, lat S]
    var w = b[2] - b[0], h = b[1] - b[3];
    if (w / h > 2) h = w / 2; else w = h * 2;
    return clampView([(b[0] + b[2]) / 2 - w / 2, -(b[1] + b[3]) / 2 - h / 2, w, h]);
  }
  function zoomView(v, px, py, f) { // zoom by f around (px, py), fractions of the map
    var w = Math.min(360, Math.max(MIN_W, v[2] * f)), r = w / v[2];
    return clampView([v[0] + px * v[2] * (1 - r), v[1] + py * v[3] * (1 - r), w]);
  }
  var REGIONS = {
    world: null, europe: [-25, 71, 45, 33], africa: [-20, 38, 58, -36], asia: [25, 78, 150, -12],
    north_america: [-170, 83, -50, 7], south_america: [-90, 14, -30, -56], oceania: [105, 0, 180, -50],
    antarctica: [-180, -60, 180, -90],
  };

  var core = { decode: decode, tally: tally, order: order, toHash: toHash, fromHash: fromHash,
    clampView: clampView, boxView: boxView, zoomView: zoomView, FULL: FULL, REGIONS: REGIONS };
  if (typeof document === "undefined") { module.exports = core; return; } // tests (node)

  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------------ carousel
  (function () {
    var box = document.querySelector("[data-carousel]");
    if (!box) return;
    var slides = Array.prototype.slice.call(box.querySelectorAll(".feature__slide"));
    var ctrl = box.querySelector(".feature__ctrl"), bars = box.querySelectorAll(".bar");
    var play = box.querySelector("[data-play]"), countEl = box.querySelector("[data-count]");
    var DUR = 8000, i = 0, elapsed = 0, last = null, paused = reduced, holding = false;
    if (slides.length < 2) return;
    ctrl.hidden = false;
    function show(n) {
      i = (n + slides.length) % slides.length; elapsed = 0; // circular
      slides.forEach(function (s, j) { s.classList.toggle("is-on", j === i); s.inert = j !== i; });
      bars.forEach(function (b, j) {
        b.classList.toggle("done", j < i); b.querySelector("b").style.transform = "";
        b.setAttribute("aria-current", j === i ? "true" : "false");
      });
      countEl.textContent = (i + 1) + " / " + slides.length;
    }
    function setPaused(p) {
      paused = p; box.classList.toggle("is-paused", p);
      play.textContent = p ? "▶" : "❚❚";
      play.setAttribute("aria-label", p ? box.dataset.play : box.dataset.pause);
    }
    // The clock runs here, not in CSS: requestAnimationFrame stops when the tab is
    // hidden, and pausing is exact.
    function tick(t) {
      if (last != null && !paused && !holding) elapsed += t - last;
      last = t;
      bars[i].querySelector("b").style.transform = "scaleX(" + Math.min(1, elapsed / DUR) + ")";
      if (elapsed >= DUR) show(i + 1);
      requestAnimationFrame(tick);
    }
    bars.forEach(function (b, j) { b.addEventListener("click", function () { show(j); }); });
    box.querySelector("[data-prev]").addEventListener("click", function () { show(i - 1); });
    box.querySelector("[data-next]").addEventListener("click", function () { show(i + 1); });
    play.addEventListener("click", function () { setPaused(!paused); });
    box.addEventListener("mouseenter", function () { holding = true; });
    box.addEventListener("mouseleave", function () { holding = false; });
    box.addEventListener("focusin", function (e) { holding = e.target.matches(":focus-visible"); }); // keyboard only
    box.addEventListener("focusout", function () { holding = false; });
    var x0 = null, swiped = false; // a swipe changes the slide and must not open the page
    box.addEventListener("pointerdown", function (e) { x0 = e.clientX; swiped = false; });
    box.addEventListener("pointerup", function (e) {
      if (x0 != null && Math.abs(e.clientX - x0) > 50) { swiped = true; show(i + (e.clientX < x0 ? 1 : -1)); }
      x0 = null;
    });
    box.addEventListener("click", function (e) { if (swiped) { e.preventDefault(); swiped = false; } }, true);
    setPaused(paused);
    show(0);
    requestAnimationFrame(tick);
  })();

  // ------------------------------------------------------------------ explorer
  var root = document.querySelector("[data-explore]");
  if (!root) return;
  var S = JSON.parse(root.querySelector("[data-strings]").textContent);
  var lang = root.dataset.lang, nf = new Intl.NumberFormat(lang === "es" ? "es-ES" : "en-GB");
  function num(n) { var s = nf.format(n); return lang === "es" ? s.replace(/\./g, " ") : s; }
  function fill(tpl, v) { return tpl.replace(/\{(\w+)\}/g, function (_, k) { return v[k]; }); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  var segs = root.querySelectorAll(".ribbon__seg"), tiles = root.querySelectorAll(".gtile");
  var svg = root.querySelector(".mapbox svg"), spots = svg.querySelectorAll("a[data-code]");
  var select = root.querySelector("[data-country]"), results = root.querySelector("[data-results]");
  var countEl = root.querySelector("[data-count]"), pills = root.querySelector("[data-pills]");
  var orderEl = root.querySelector("[data-order]"), empty = root.querySelector("[data-empty]");
  var moreLink = root.querySelector("[data-more]");
  var D = null, taxa = null, keys = null, st = { scope: "new", time: null, group: null, place: null };
  var page = 1, PAGE = 12, loading = null;

  ["[data-scope]", ".mapctl", ".maphint", ".mapfoot"].forEach(function (s) {
    var e = root.querySelector(s); if (e) (e.closest(".scope") || e).hidden = false;
  });

  function ensure() {
    if (!loading) {
      loading = fetch(root.dataset.index).then(function (r) { return r.json(); }).then(function (ix) {
        D = ix; taxa = decode(ix);
        keys = { time: ix.periods.map(function (p) { return p[0]; }), group: ix.groups.map(function (g) { return g[0]; }),
          place: ix.countries.map(function (c) { return c[0]; }) };
      });
    }
    return loading;
  }
  // Load when the explorer comes into view, so the first tap answers at once.
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { ensure(); io.disconnect(); } }, { rootMargin: "200px" });
    io.observe(root);
  }

  function card(t) {
    var a = el("a", "card"); a.href = t.u;
    if (t.img) {
      var img = el("img", "pic pic--card" + (t.flags & SILHOUETTE ? " pic--silhouette" : ""));
      img.src = t.img; img.alt = t.n; img.loading = "lazy"; img.decoding = "async"; a.appendChild(img);
    } else {
      var ph = el("div", "pic pic--card pic--empty", "✶"); ph.setAttribute("aria-hidden", "true"); a.appendChild(ph);
    }
    var body = el("span", "card__body"), name = el("span", "card__name");
    name.appendChild(el("em", null, t.n)); body.appendChild(name); body.appendChild(el("span", "card__meta", t.meta));
    a.appendChild(body);
    if (st.scope === "all" && t.flags & CURIOSITIES) { a.classList.add("card--fact"); a.dataset.badge = S.badge; }
    return a;
  }

  function render() {
    var tl = tally(taxa, st, { time: keys.time.length, group: keys.group.length, place: keys.place.length });
    var isNew = st.scope === "new";
    root.querySelectorAll("[data-scope]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.scope === st.scope)); });
    segs.forEach(function (s) {
      var i = keys.time.indexOf(s.dataset.key), n = i >= 0 ? tl.time[i] : 0;
      s.querySelector(".ribbon__n").textContent = num(n);
      s.classList.toggle("is-zero", !n); s.setAttribute("aria-pressed", String(st.time === i));
    });
    tiles.forEach(function (g) {
      var i = keys.group.indexOf(g.dataset.key), n = i >= 0 ? tl.group[i] : 0;
      g.querySelector("small").textContent = fill(isNew ? S.tile_new : S.tile_all, { n: num(n) });
      g.classList.toggle("is-zero", !n); g.setAttribute("aria-pressed", String(st.group === i));
    });
    var counts = {};
    keys.place.forEach(function (c, i) { counts[c] = tl.place[i]; });
    spots.forEach(function (a) {
      var c = a.dataset.code, n = counts[c] || 0, name = a.querySelector("title").textContent.split(" · ")[0];
      a.dataset.n = n;
      a.setAttribute("tabindex", n ? "0" : "-1");
      a.setAttribute("aria-label", fill(S.map_item, { name: name, n: num(n) }));
      a.querySelector("title").textContent = name + " · " + num(n);
      a.classList.toggle("on", st.place != null && keys.place[st.place] === c);
    });
    drawMap();
    select.value = st.place == null ? "" : keys.place[st.place];

    var found = tl.found;
    countEl.textContent = found.length === 1 ? (isNew ? S.n_new_one : S.n_all_one)
      : fill(isNew ? S.n_new : S.n_all, { n: num(found.length) });
    orderEl.textContent = isNew ? S.order_new : S.order_all;
    pills.replaceChildren();
    var active = 0;
    [["time", D.periods, 1], ["group", D.groups, 1], ["place", D.countries, 1]].forEach(function (x) {
      if (st[x[0]] == null) return;
      active++;
      var label = x[1][st[x[0]]][x[2]], p = el("span", "pill", label), b = el("button", null, "×");
      b.type = "button"; b.setAttribute("aria-label", fill(S.remove, { x: label }));
      b.addEventListener("click", function () { st[x[0]] = null; page = 1; render(); });
      p.appendChild(b); pills.appendChild(p);
    });
    if (active > 1) {
      var all = el("button", "clearall", S.clear_all); all.type = "button";
      all.addEventListener("click", function () { st.time = st.group = st.place = null; page = 1; render(); });
      pills.appendChild(all);
    }
    var list = order(found, st.scope), shown = PAGE + (page - 1) * PAGE * 2;
    results.replaceChildren.apply(results, list.slice(0, shown).map(card));
    empty.hidden = list.length > 0; empty.replaceChildren();
    if (!list.length) {
      empty.appendChild(document.createTextNode((isNew ? S.empty_new : S.empty_all) + " "));
      var alt = el("button", null, isNew ? S.empty_new_action : S.empty_all_action); alt.type = "button";
      alt.addEventListener("click", function () {
        if (isNew) st.scope = "all"; else st.time = st.group = st.place = null;
        page = 1; render();
      });
      empty.appendChild(alt);
    }
    var left = list.length - shown;
    more.hidden = left <= 0;
    more.textContent = fill(S.more, { n: num(Math.min(left, PAGE * 2)), left: num(left) });
    var h = toHash(st, keys);
    history.replaceState(null, "", h ? "#" + h : location.pathname + location.search);
  }

  // The "see all" link becomes a "show more" button once the explorer is live.
  var more = el("button", "button button--ghost"); more.type = "button"; more.hidden = true;
  more.addEventListener("click", function () { page++; render(); });

  function act(fn) { // run a change once the data is here
    return function (ev) {
      if (ev) ev.preventDefault();
      ensure().then(function () {
        if (moreLink.parentNode) moreLink.replaceWith(more);
        fn(); page = 1; render();
      });
    };
  }
  function toggle(k, key) { return act(function () { var i = keys[k].indexOf(key); st[k] = st[k] === i ? null : i; }); }
  function asButton(e, handler) { // links that act as filters with JavaScript
    e.setAttribute("role", "button"); e.setAttribute("aria-pressed", "false");
    e.addEventListener("click", handler);
    e.addEventListener("keydown", function (ev) { if (ev.key === " ") handler(ev); });
  }
  segs.forEach(function (s) { asButton(s, toggle("time", s.dataset.key)); });
  tiles.forEach(function (g) { asButton(g, toggle("group", g.dataset.key)); });
  root.querySelectorAll("[data-scope]").forEach(function (b) {
    b.addEventListener("click", act(function () { st.scope = b.dataset.scope; }));
  });
  select.addEventListener("change", act(function () {
    var code = select.value, i = keys.place.indexOf(code);
    st.place = i >= 0 ? i : null;
    var c = D.countries[i];
    if (c) animateTo(clampView([c[3] - 25, -c[2] - 12.5, 50])); // fly to the country
  }));

  // ----------------------------------------------------------------------- map
  var view = FULL.slice(), anim = null, dragged = false;
  var labels = document.createElementNS("http://www.w3.org/2000/svg", "g");
  labels.setAttribute("class", "map__labels"); labels.setAttribute("aria-hidden", "true");
  svg.appendChild(labels);
  function radius(n, k) {
    var big = st.scope === "new" ? 1.3 : 0.42, s = Math.pow(k, 0.9);
    return n ? Math.max(1.3 * s, Math.sqrt(n) * big * s) : 0;
  }
  var land = svg.querySelector("use[data-detail]");
  function drawMap() {
    var k = view[2] / 360;
    if (land && k < 1) { land.setAttribute("href", land.dataset.detail); land = null; } // 1:50m on the first zoom
    svg.setAttribute("viewBox", view.join(" "));
    var placed = [], visible = [];
    spots.forEach(function (a) {
      var c = a.querySelector("circle"), n = +(a.dataset.n || 0), r = radius(n, k);
      c.setAttribute("r", r);
      c.setAttribute("stroke-width", 0.35 * k);
      var x = +c.getAttribute("cx"), y = +c.getAttribute("cy");
      if (r && x > view[0] && x < view[0] + view[2] && y > view[1] && y < view[1] + view[3]) visible.push([n, x, y, r, a]);
    });
    labels.replaceChildren();
    if (k < 0.6) { // names of the biggest visible countries, never overlapping
      visible.sort(function (a, b) { return b[0] - a[0]; }).slice(0, 14).forEach(function (v) {
        var name = v[4].querySelector("title").textContent.split(" · ")[0];
        var fs = 9.5 * k, y = v[2] - v[3] - 1.2 * k, w = name.length * fs * 0.56;
        var box = [v[1] - w / 2, y - fs, v[1] + w / 2, y + fs * 0.2];
        if (placed.some(function (p) { return box[0] < p[2] && box[2] > p[0] && box[1] < p[3] && box[3] > p[1]; })) return;
        placed.push(box);
        var t = document.createElementNS("http://www.w3.org/2000/svg", "text");
        t.setAttribute("x", v[1]); t.setAttribute("y", y); t.setAttribute("font-size", fs);
        t.setAttribute("stroke-width", 2.2 * k); t.textContent = name; labels.appendChild(t);
      });
    }
  }
  function pressRegion(name) {
    root.querySelectorAll("[data-region]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.region === name)); });
  }
  function animateTo(target, name) {
    var from = view.slice(), t0 = performance.now(), dur = reduced ? 0 : 450;
    cancelAnimationFrame(anim);
    (function step(t) {
      var p = dur ? Math.min(1, (t - t0) / dur) : 1, e = 1 - Math.pow(1 - p, 3);
      view = from.map(function (x, j) { return x + (target[j] - x) * e; });
      drawMap();
      if (p < 1) anim = requestAnimationFrame(step);
    })(t0);
    pressRegion(name);
  }
  root.querySelectorAll("[data-region]").forEach(function (b) {
    b.addEventListener("click", function () { var r = REGIONS[b.dataset.region]; animateTo(r ? boxView(r) : FULL, b.dataset.region); });
  });
  root.querySelectorAll("[data-zoom]").forEach(function (b) {
    b.addEventListener("click", function () {
      var z = b.dataset.zoom;
      if (z === "world") animateTo(FULL, "world");
      else { view = zoomView(view, 0.5, 0.5, z === "in" ? 0.6 : 1 / 0.6); drawMap(); pressRegion(null); }
    });
  });
  spots.forEach(function (a) {
    var handler = function (ev) {
      ev.preventDefault();
      if (dragged) return;
      act(function () { var i = keys.place.indexOf(a.dataset.code); st.place = st.place === i ? null : i; })();
    };
    a.addEventListener("click", handler);
    a.addEventListener("keydown", function (ev) { if (ev.key === " ") handler(ev); });
  });
  // Pointers: one drags, two pinch. The pointer is captured only once it really moves,
  // so a tap still reaches the country under it.
  var ptrs = new Map(), start = null;
  function rel(e) { var r = svg.getBoundingClientRect(); return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]; }
  svg.addEventListener("pointerdown", function (e) {
    ptrs.set(e.pointerId, [e.clientX, e.clientY]); dragged = false; cancelAnimationFrame(anim);
    start = { view: view.slice(), pts: Array.from(ptrs.values()) };
  });
  svg.addEventListener("pointermove", function (e) {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    var r = svg.getBoundingClientRect(), a = Array.from(ptrs.values()), b = start.pts;
    if (a.length === 1 && b.length === 1) {
      var dx = a[0][0] - b[0][0], dy = a[0][1] - b[0][1];
      if (!dragged && Math.hypot(dx, dy) < 4) return;
      if (!dragged) { dragged = true; svg.setPointerCapture(e.pointerId); svg.classList.add("is-dragging"); pressRegion(null); }
      view = clampView([start.view[0] - dx / r.width * start.view[2], start.view[1] - dy / r.height * start.view[3], start.view[2]]);
      drawMap();
    } else if (a.length === 2 && b.length === 2) {
      dragged = true; pressRegion(null);
      var d0 = Math.hypot(b[0][0] - b[1][0], b[0][1] - b[1][1]), d1 = Math.hypot(a[0][0] - a[1][0], a[0][1] - a[1][1]);
      var mx = ((a[0][0] + a[1][0]) / 2 - r.left) / r.width, my = ((a[0][1] + a[1][1]) / 2 - r.top) / r.height;
      if (d1 > 0) { view = zoomView(start.view, mx, my, d0 / d1); drawMap(); }
    }
  });
  function end(e) {
    ptrs.delete(e.pointerId); svg.classList.remove("is-dragging");
    start = { view: view.slice(), pts: Array.from(ptrs.values()) };
    setTimeout(function () { dragged = false; }, 0);
  }
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  svg.addEventListener("wheel", function (e) {
    e.preventDefault(); var p = rel(e);
    view = zoomView(view, p[0], p[1], e.deltaY > 0 ? 1.2 : 1 / 1.2); drawMap(); pressRegion(null);
  }, { passive: false });
  svg.addEventListener("dblclick", function (e) { var p = rel(e); view = zoomView(view, p[0], p[1], 0.5); drawMap(); pressRegion(null); });
  pressRegion("world");

  // A shared link with filters (#all&time=…) opens in that state.
  if (location.hash.length > 1 && /(^#|&)(all|time|group|place)/.test(location.hash)) {
    ensure().then(function () {
      st = fromHash(location.hash, keys);
      if (moreLink.parentNode) moreLink.replaceWith(more);
      render();
    });
  }
})();
