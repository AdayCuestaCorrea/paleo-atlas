// Paleo Atlas search: runs in the browser over a small JSON index (search.py).
// Ignores accents and case, strips plurals, matches prefixes and tolerates small
// typos; weights matches by field and offers facets to narrow the results.
(function () {
  "use strict";
  var STOP = new Set(["de", "del", "la", "las", "el", "los", "en", "y", "the", "of", "and", "in", "a"]);
  var FACETS = ["clade", "group", "time", "place"];
  var taxa = [], weights = {}, facet = null, timer = null;

  function norm(s) {
    return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, " ").trim();
  }
  function stem(w) {
    if (w.length > 5 && /[^aeiou]es$/.test(w)) return w.slice(0, -2); // raptores
    if (w.length > 3 && w.endsWith("s") && !w.endsWith("us") && !w.endsWith("is")) return w.slice(0, -1);
    return w;
  }
  function words(s) {
    // One-letter words are initials ("T. rex"): the epithet alone finds the species.
    return norm(s).split(" ").filter(function (w) { return w.length > 1 && !STOP.has(w); }).map(stem);
  }
  function lev(a, b, max) { // Levenshtein distance, giving up above max
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      var best = i;
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      prev = cur;
    }
    return prev[b.length];
  }
  // How well one query word matches one index word (0 = not at all).
  function quality(q, t) {
    if (t === q) return 1;
    if (t.startsWith(q)) return q.length >= 3 ? 0.8 : 0;
    if (q.length < 4 || q[0] !== t[0]) return 0; // typos rarely hit the first letter
    var max = q.length >= 8 ? 2 : 1;
    var d = Math.min(lev(q, t, max), lev(q, t.slice(0, q.length), max));
    return d <= max ? 0.5 : 0;
  }

  // Format 2 (search.py): [name, meta, image, flags, fields, facets, key?], every
  // text an id into index.terms; fields and facets by position; the page key follows
  // from the name unless given.
  function expand(index, t) {
    var T = index.terms, f = {}, x = {};
    index.fields.forEach(function (k, i) {
      if (t[4][i].length) f[k] = t[4][i].map(function (j) { return T[j]; });
    });
    index.facets.forEach(function (k, i) {
      var v = t[5][i];
      if (Array.isArray(v) ? v.length : v != null) {
        x[k] = Array.isArray(v) ? v.map(function (j) { return T[j]; }) : T[v];
      }
    });
    var img = t[2] == null ? null : T[t[2]], bar = img ? img.indexOf("|") : -1;
    if (bar > 0) img = index.images[+img.slice(0, bar)] + img.slice(bar + 1);
    var key = t[6] || t[0].trim().replace(/[^A-Za-z0-9]+/g, "-").toLowerCase();
    return {
      n: t[0], u: index.url[0] + key + index.url[1], img: img, sil: !!(t[3] & 1),
      new: !!(t[3] & 2), meta: t[1] == null ? "" : T[t[1]], f: f, facets: x,
    };
  }

  function prepare(index) {
    weights = index.weights;
    var raw = index.v === 2 ? index.taxa.map(function (t) { return expand(index, t); }) : index.taxa;
    taxa = raw.map(function (t) {
      var tokens = [];
      Object.keys(t.f).forEach(function (field) {
        t.f[field].forEach(function (text) {
          words(text).forEach(function (w) { tokens.push([w, field]); });
        });
      });
      t.tokens = tokens;
      return t;
    });
  }

  function search(query) {
    var qs = words(query);
    if (!qs.length) return [];
    var out = [];
    taxa.forEach(function (t) {
      var score = 0, fields = {};
      for (var i = 0; i < qs.length; i++) {
        var best = 0, bestField = null;
        t.tokens.forEach(function (tok) {
          var s = quality(qs[i], tok[0]) * weights[tok[1]];
          if (s > best) { best = s; bestField = tok[1]; }
        });
        if (!best) return; // every word must match something
        score += best;
        fields[bestField] = true;
      }
      out.push({ t: t, score: score + (t.new ? 0.5 : 0), fields: fields });
    });
    return out.sort(function (a, b) { return b.score - a.score || a.t.n.localeCompare(b.t.n); });
  }

  if (typeof document === "undefined") { // tests (node): only the matching logic
    module.exports = { prepare: prepare, search: search, words: words, taxa: function () { return taxa; } };
    return;
  }
  // The index, downloaded once per page and only when needed.
  var loading = null;
  function load(url) {
    if (!loading) {
      loading = fetch(url).then(function (r) { return r.json(); }).then(function (index) { prepare(index); });
    }
    return loading;
  }
  window.PaleoSearch = { load: load, search: search };

  // Suggestions under the search box of the header, on every page.
  document.querySelectorAll("[data-suggest]").forEach(function (form) {
    var input = form.querySelector("input[name=q]"), list = form.querySelector(".suggest"), timer = null;
    function hide() { list.hidden = true; input.setAttribute("aria-expanded", "false"); }
    input.addEventListener("focus", function () { load(form.dataset.index); });
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        load(form.dataset.index).then(function () {
          var q = input.value.trim(), found = q ? search(q) : [];
          list.replaceChildren();
          if (!q) { hide(); return; }
          found.slice(0, 6).forEach(function (r) {
            var li = document.createElement("li"), a = document.createElement("a");
            a.href = r.t.u;
            var img = document.createElement(r.t.img ? "img" : "span");
            if (r.t.img) { img.src = r.t.img; img.alt = ""; img.loading = "lazy"; if (r.t.sil) img.className = "pic--silhouette"; }
            var text = document.createElement("span"), name = document.createElement("em"), meta = document.createElement("small");
            name.textContent = r.t.n; meta.textContent = r.t.meta;
            text.append(name, meta); a.append(img, text); li.appendChild(a); list.appendChild(li);
          });
          var li = document.createElement("li"), all = document.createElement("a");
          all.className = "suggest__all";
          all.href = form.action + "?q=" + encodeURIComponent(q);
          all.textContent = found.length ? form.dataset.all.replace("{n}", found.length) : form.dataset.none;
          li.appendChild(all); list.appendChild(li);
          list.hidden = false; input.setAttribute("aria-expanded", "true");
        });
      }, 120);
    });
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") hide();
      if (ev.key === "ArrowDown") { var a = list.querySelector("a"); if (a && !list.hidden) { ev.preventDefault(); a.focus(); } }
    });
    list.addEventListener("keydown", function (ev) {
      var links = Array.prototype.slice.call(list.querySelectorAll("a")), i = links.indexOf(document.activeElement);
      if (ev.key === "ArrowDown" && i < links.length - 1) { ev.preventDefault(); links[i + 1].focus(); }
      if (ev.key === "ArrowUp") { ev.preventDefault(); (i > 0 ? links[i - 1] : input).focus(); }
      if (ev.key === "Escape") { hide(); input.focus(); }
    });
    // Keep the focus in the box while a suggestion is pressed: nothing moves between the
    // press and the release, so the click opens the page that was under the pointer.
    list.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
    document.addEventListener("click", function (ev) { if (!form.contains(ev.target)) hide(); });
  });

  var root = document.querySelector("[data-search]");
  if (!root) return;
  var input = root.querySelector("input[name=q]");
  var results = root.querySelector(".search__results");
  var chips = root.querySelector(".search__chips");
  var count = root.querySelector(".search__count");
  var empty = root.querySelector(".search__empty");
  var strings = root.querySelector("#search-strings").dataset;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }
  function card(t) {
    var a = el("a", "card");
    a.href = t.u;
    if (t.img) {
      var img = el("img", "pic pic--card" + (t.sil ? " pic--silhouette" : ""));
      img.src = t.img; img.alt = t.n; img.loading = "lazy"; img.decoding = "async";
      a.appendChild(img);
    } else {
      var ph = el("div", "pic pic--card pic--empty", "✶");
      ph.setAttribute("aria-hidden", "true");
      a.appendChild(ph);
    }
    var body = el("span", "card__body");
    var name = el("span", "card__name");
    name.appendChild(el("em", null, t.n));
    body.appendChild(name);
    body.appendChild(el("span", "card__meta", t.meta));
    a.appendChild(body);
    return a;
  }
  function chip(label, value, active) {
    var b = el("button", "chip" + (active ? " chip--on" : ""), label);
    b.type = "button";
    b.setAttribute("aria-pressed", active ? "true" : "false");
    b.addEventListener("click", function () { facet = value; render(); });
    return b;
  }

  function render() {
    var query = input.value;
    var found = search(query);
    // Facets of the fields the query matched ("abelisauridos" -> Abelisauridae (4)).
    // A taxon can span several periods: only the ones the query asked for count.
    var qs = words(query);
    function values(r, f) {
      var v = r.t.facets[f];
      if (!v || !r.fields[f]) return [];
      if (!Array.isArray(v)) return [v];
      return v.filter(function (x) {
        return words(x).some(function (w) { return qs.some(function (q) { return quality(q, w) > 0; }); });
      });
    }
    var counts = {};
    found.forEach(function (r) {
      FACETS.forEach(function (f) {
        values(r, f).forEach(function (v) { counts[f + "\u0000" + v] = (counts[f + "\u0000" + v] || 0) + 1; });
      });
    });
    var keys = Object.keys(counts).filter(function (k) { return counts[k] >= 2; })
      .sort(function (a, b) { return counts[b] - counts[a]; }).slice(0, 8);
    if (facet && keys.indexOf(facet) < 0) facet = null;
    chips.replaceChildren();
    if (keys.length > 1 || (keys.length === 1 && counts[keys[0]] < found.length)) {
      chips.appendChild(chip(strings.all, null, !facet));
      keys.forEach(function (k) {
        chips.appendChild(chip(k.split("\u0000")[1] + " (" + counts[k] + ")", k, facet === k));
      });
    }
    if (facet) {
      var parts = facet.split("\u0000");
      found = found.filter(function (r) {
        var v = r.t.facets[parts[0]];
        return Array.isArray(v) ? v.indexOf(parts[1]) >= 0 : v === parts[1];
      });
    }
    results.replaceChildren.apply(results, found.slice(0, 60).map(function (r) { return card(r.t); }));
    count.textContent = !query.trim() ? "" :
      found.length === 1 ? strings.one : strings.results.replace("{n}", found.length);
    empty.hidden = !query.trim() || found.length > 0;
    empty.querySelector("a").href = root.dataset.wiki + encodeURIComponent(query.trim());
    var url = new URL(location.href);
    if (query.trim()) url.searchParams.set("q", query.trim()); else url.searchParams.delete("q");
    history.replaceState(null, "", url);
  }

  root.querySelector("form").addEventListener("submit", function (ev) {
    ev.preventDefault(); // Enter opens the first result
    var first = results.querySelector("a");
    if (first) location.href = first.href;
  });
  input.addEventListener("input", function () {
    facet = null;
    clearTimeout(timer);
    timer = setTimeout(render, 120);
  });
  input.addEventListener("keydown", function (ev) {
    var first = results.querySelector("a");
    if (ev.key === "ArrowDown" && first) { ev.preventDefault(); first.focus(); }
  });

  load(root.dataset.index).then(function () {
    var q = new URL(location.href).searchParams.get("q");
    if (q) input.value = q;
    render();
  });
})();
