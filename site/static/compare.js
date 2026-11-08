/* Size comparator (ALCANCE.md §11.3): the card on a taxon page, the window it opens
   and the page of its own (es/comparador.html, en/size.html).
   1. Core: pure functions (box, layout, scale, grid step, clamp, drag threshold,
      picking by the drawing, hash). Tested with node (tests/test_compare_js.py).
   2. UI: card preview, <dialog> or page, stage with draggable silhouettes. */
(() => {
  "use strict";

  // ===================================================================== 1. Core
  const DRAG_PX = 8; // below this a press is a click, not a drag

  const Core = {
    /** Bounding box in metres at the "min" or "max" size. Own drawings carry their
     * box; a silhouette's height comes from its proportions (not measured). */
    box(it, which) {
      const v = which === "min" ? it.lo : it.hi;
      if (it.box) { const f = v / it.hi; return { w: it.box[0] * f, h: it.box[1] * f }; }
      return it.ax === "height" ? { w: v / it.a, h: v } : { w: v, h: v * it.a };
    },
    gap(boxes) {
      return Math.max(0.15, 0.07 * Math.max(...boxes.map((b) => b.w)));
    },
    /** Items side by side on the ground, in metres. */
    layout(boxes) {
      const g = Core.gap(boxes);
      let x = g;
      return boxes.map((b) => { const p = { x, y: 0 }; x += b.w + g; return p; });
    },
    /** Pixels per metre so that every item, where it is, fits the stage. */
    scale(boxes, pos, W, H, pad) {
      const g = Core.gap(boxes);
      const wM = Math.max(...boxes.map((b, i) => pos[i].x + b.w)) + g;
      const hM = Math.max(...boxes.map((b, i) => pos[i].y + b.h)) * 1.22;
      return Math.min((W - pad.l - pad.r) / wM, (H - pad.t - pad.b) / hM);
    },
    /** Grid step in metres: lines at least minPx apart. */
    step(pxPerM, minPx = 46) {
      for (const s of [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 50, 100]) if (s * pxPerM >= minPx) return s;
      return 200;
    },
    clamp(p, b, worldW, worldH) {
      return {
        x: Math.min(Math.max(p.x, 0), Math.max(0, worldW - b.w)),
        y: Math.min(Math.max(p.y, 0), Math.max(0, worldH - b.h)),
      };
    },
    isDrag(dx, dy) { return Math.hypot(dx, dy) >= DRAG_PX; },
    /** Ink at (u, v) of a silhouette? u, v in 0..1 from its top left; mask = {w, h, a}
     * (alpha bytes); r cells of tolerance so thin tails and legs can be grabbed. */
    inked(mask, u, v, r = 1) {
      if (u < 0 || u > 1 || v < 0 || v > 1) return false;
      const cx = Math.min(mask.w - 1, Math.floor(u * mask.w)), cy = Math.min(mask.h - 1, Math.floor(v * mask.h));
      for (let y = Math.max(0, cy - r); y <= Math.min(mask.h - 1, cy + r); y++)
        for (let x = Math.max(0, cx - r); x <= Math.min(mask.w - 1, cx + r); x++) if (mask.a[y * mask.w + x] > 40) return true;
      return false;
    },
    /** Topmost item whose drawing (not its box) is under (px, py), in px from the
     * stage's bottom left; tiny items count by their box plus a margin. */
    pick(items, px, py, tolPx = 3) {
      const order = items.slice().sort((a, b) => b.z - a.z);
      for (const it of order) {
        if (!it.rect) continue;
        const { l, b, w, h } = it.rect, pad = w < 24 || h < 24 ? 8 : 0;
        if (px < l - pad || px > l + w + pad || py < b - pad || py > b + h + pad) continue;
        if (pad || !it.mask) return it;
        if (Core.inked(it.mask, (px - l) / w, 1 - (py - b) / h, Math.ceil((tolPx * it.mask.w) / w))) return it;
      }
      return null;
    },
    /** Item keys in the URL: "#comparar=tyrannosaurus,man" (or "#compare=…"). */
    parseHash(h) {
      const m = /(?:comparar|compare)=([^&]*)/.exec(h || "");
      return m ? decodeURIComponent(m[1]).split(",").filter(Boolean).slice(0, 6) : [];
    },
    hash(name, keys) { return "#" + name + "=" + keys.join(","); },
    len(v, lang) {
      if (v < 1) return Math.round(v * 100) + " cm";
      const d = v < 10 ? 2 : 1;
      return (+v.toFixed(d)).toLocaleString(lang, { maximumFractionDigits: d }) + " m";
    },
    range(lo, hi, lang) {
      if (lo === hi) return Core.len(hi, lang);
      if (hi < 1) return Math.round(lo * 100) + "–" + Core.len(hi, lang);
      return Core.len(lo, lang).replace(/ c?m$/, "") + "–" + Core.len(hi, lang);
    },
  };
  if (typeof document === "undefined") { module.exports = Core; return; } // tests (node)

  // ===================================================================== 2. UI
  // Silhouette colours from the CSS token --cmp (light and dark mode), read when drawn.
  const palette = () => {
    const v = getComputedStyle(document.documentElement).getPropertyValue("--cmp").trim();
    return v ? v.split(/\s+/) : ["#2c6b55", "#b07a1f", "#3f6e9c", "#8a4f7d", "#6e7f2e", "#4a5560"];
  };
  const KINDS = ["taxon", "people", "animals", "objects"];
  const MAX_ITEMS = 6;
  const LIST_LIMIT = 30;
  const ISSUES = "https://github.com/AdayCuestaCorrea/paleo-atlas/issues/new";
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const fill = (s, kv) => s.replace(/\{(\w+)\}/g, (_, k) => (k in kv ? kv[k] : ""));
  const maskStyle = (src) => `-webkit-mask-image:url("${src}");mask-image:url("${src}")`;
  const link = (href, text) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>`;

  let IX = null, CATALOG = null, L = null, LANG = "es";
  const indexes = new Map();
  function loadIndex(url) {
    if (!indexes.has(url)) indexes.set(url, fetch(url).then((r) => r.json()).then((ix) => {
      IX = ix; L = ix.labels; LANG = ix.lang; CATALOG = new Map();
      ix.taxa.forEach((t) => CATALOG.set(t.k, { ...t, kind: "taxon", ax: "length", italic: true }));
      ix.refs.forEach((r) => CATALOG.set(r.k, r));
      return ix;
    }));
    return indexes.get(url);
  }

  // Alpha of each silhouette, drawn once on a canvas, to pick by the drawing.
  const MASKS = new Map();
  function loadMask(src, aspect) {
    if (!MASKS.has(src)) MASKS.set(src, new Promise((res) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        try {
          const R = 256, w = aspect >= 1 ? Math.max(8, Math.round(R / aspect)) : R, h = aspect >= 1 ? R : Math.max(8, Math.round(R * aspect));
          const c = document.createElement("canvas"); c.width = w; c.height = h;
          const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0, w, h);
          const d = g.getImageData(0, 0, w, h).data, a = new Uint8Array(w * h);
          for (let i = 0; i < w * h; i++) a[i] = d[i * 4 + 3];
          res({ w, h, a });
        } catch { res(null); } // no CORS: pick by the box
      };
      img.onerror = () => res(null);
      img.src = src;
    }));
    return MASKS.get(src);
  }
  const aspectOf = (it) => (it.box ? it.box[1] / it.box[0] : it.a);
  const label = (it) => (it.italic ? `<i>${esc(it.n)}</i>` : esc(it.n));
  const sizeText = (it) => Core.range(it.lo, it.hi, LANG);

  // ------------------------------------------------------------ the stage
  class Stage {
    constructor(host, opts = {}) {
      this.host = host; this.opts = opts; this.items = []; this.which = "max"; this.sel = null; this.z = 1;
      host.classList.add("cmp-stage");
      if (!REDUCED && !opts.static) host.classList.add("cmp-anim");
      this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      this.svg.setAttribute("class", "cmp-grid"); this.svg.setAttribute("aria-hidden", "true");
      host.append(this.svg);
      if (!opts.static) { host.append(el("p", "cmp-hint", esc(L.cmp_hint))); this.pointer(); }
      new ResizeObserver(() => this.draw()).observe(host);
    }
    pad() { return this.opts.static ? { l: 6, r: 6, t: 4, b: 6 } : { l: 46, r: 16, t: 34, b: 30 }; }
    set(keys, keep) {
      const old = new Map(this.items.map((i) => [i.k, i])), pal = palette();
      this.items = keys.map((k, n) => {
        const prev = keep && old.get(k);
        return { ...CATALOG.get(k), color: pal[n % pal.length], pos: prev ? prev.pos : null, z: prev ? prev.z : ++this.z };
      });
      const boxes = this.boxes(), lay = Core.layout(boxes);
      // Keep where the user put things; new items go to the right of everything.
      let right = 0;
      this.items.forEach((it, i) => { if (it.pos) right = Math.max(right, it.pos.x + boxes[i].w); });
      this.items.forEach((it, i) => {
        if (it.pos) return;
        it.pos = keep && right ? { x: right + Core.gap(boxes), y: 0 } : lay[i];
        if (keep && right) right = it.pos.x + boxes[i].w;
      });
      this.fit(); this.render();
    }
    boxes() { return this.items.map((i) => Core.box(i, this.which)); }
    fit() {
      const r = this.host.getBoundingClientRect();
      this.W = r.width || 600; this.H = r.height || 300;
      this.s = this.items.length ? Core.scale(this.boxes(), this.items.map((i) => i.pos), this.W, this.H, this.pad()) : 50;
    }
    relayout() { const lay = Core.layout(this.boxes()); this.items.forEach((it, i) => (it.pos = lay[i])); this.fit(); this.draw(); }
    render() {
      this.host.querySelectorAll(".cmp-sil,.cmp-tag").forEach((n) => n.remove());
      this.items.forEach((it) => {
        const node = el("div", "cmp-sil");
        node.style.cssText = maskStyle(it.s) + `;background:${it.color}`;
        if (!this.opts.static) {
          node.tabIndex = 0; node.setAttribute("role", "button");
          node.setAttribute("aria-label", fill(L.cmp_aria, { name: it.n, size: sizeText(it) }));
          this.keys(node, it);
          loadMask(it.s, aspectOf(it)).then((m) => (it.mask = m));
        }
        const tag = el("div", "cmp-tag");
        it.node = node; it.tag = tag;
        this.host.append(node, tag);
      });
      this.draw();
    }
    draw() {
      if (!this.items.length) { this.svg.innerHTML = ""; return; }
      const r = this.host.getBoundingClientRect();
      if (Math.abs(r.width - this.W) > 1 || Math.abs(r.height - this.H) > 1) this.fit();
      const { s, W, H } = this, pad = this.pad(), ground = H - pad.b, boxes = this.boxes();
      let g = "";
      if (!this.opts.static) {
        const st = Core.step(s);
        for (let v = 0; ground - v * s >= 0; v += st) {
          const y = ground - v * s;
          g += `<line x1="${pad.l}" x2="${W}" y1="${y}" y2="${y}"${v === 0 ? ' class="ground"' : ""}/>`;
          if (v > 0) g += `<text x="${pad.l - 6}" y="${y + 4}" text-anchor="end">${Core.len(v, LANG)}</text>`;
        }
        for (let v = st; pad.l + v * s < W; v += st) g += `<line x1="${pad.l + v * s}" x2="${pad.l + v * s}" y1="${ground}" y2="${ground + 5}"/>`;
      } else g = `<line class="ground" x1="0" x2="${W}" y1="${ground}" y2="${ground}"/>`;
      this.svg.innerHTML = g;
      this.items.forEach((it, i) => {
        const b = boxes[i], w = b.w * s, h = b.h * s;
        it.rect = { l: pad.l + it.pos.x * s, b: pad.b + it.pos.y * s, w: Math.max(w, 2), h: Math.max(h, 2) };
        Object.assign(it.node.style, { left: it.rect.l + "px", bottom: it.rect.b + "px", width: it.rect.w + "px", height: it.rect.h + "px", zIndex: it.z });
        it.tag.style.zIndex = it.z;
        it.tag.className = "cmp-tag" + (h < 14 ? " is-tiny" : "");
        it.tag.innerHTML = this.opts.static ? "" : `<b>${label(it)}</b>${Core.len(this.which === "min" ? it.lo : it.hi, LANG)}`;
        it.tagAt = { x: it.rect.l + w / 2, y: it.rect.b + it.rect.h + 3 };
        it.node.classList.toggle("is-selected", this.sel === it.k);
      });
      // Labels must not cover each other: lift a label above any earlier one it overlaps.
      const placed = [];
      this.items.forEach((it) => {
        const tw = it.tag.offsetWidth || 80, th = it.tag.offsetHeight || 26;
        let y = it.tagAt.y;
        for (let again = true; again;) {
          again = false;
          for (const p of placed) if (Math.abs(p.x - it.tagAt.x) < (p.w + tw) / 2 && y < p.y + p.h && y + th > p.y) { y = p.y + p.h + 2; again = true; }
        }
        const x = Math.min(Math.max(it.tagAt.x, tw / 2 + 2), W - tw / 2 - 2);
        placed.push({ x, y, w: tw, h: th });
        Object.assign(it.tag.style, { left: x + "px", bottom: y + "px" });
      });
    }
    world() { const pad = this.pad(); return { w: (this.W - pad.l - pad.r) / this.s, h: (this.H - pad.t - pad.b) / this.s }; }
    move(it, x, y) {
      const wd = this.world();
      it.pos = Core.clamp({ x, y }, Core.box(it, this.which), wd.w, wd.h);
      this.draw();
    }
    /** Pointer events on the whole stage: the silhouette grabbed is the topmost one
     * with ink under the finger or cursor, so a transparent corner never steals it. */
    pointer() {
      const host = this.host;
      let start = null;
      const at = (e) => { const r = host.getBoundingClientRect(); return [e.clientX - r.left, r.bottom - e.clientY]; };
      host.addEventListener("pointerdown", (e) => {
        if (e.button !== 0) return;
        const it = Core.pick(this.items, ...at(e));
        if (!it) return;
        e.preventDefault();
        host.setPointerCapture(e.pointerId);
        start = { it, x: e.clientX, y: e.clientY, px: it.pos.x, py: it.pos.y, moved: false };
        it.z = ++this.z; this.draw();
      });
      host.addEventListener("pointermove", (e) => {
        if (!start) { if (e.pointerType === "mouse") host.style.cursor = Core.pick(this.items, ...at(e)) ? "grab" : ""; return; }
        const dx = e.clientX - start.x, dy = e.clientY - start.y;
        if (!start.moved && !Core.isDrag(dx, dy)) return;
        start.moved = true; start.it.node.classList.add("is-dragging"); host.style.cursor = "grabbing";
        this.move(start.it, start.px + dx / this.s, start.py - dy / this.s);
      });
      const end = (e) => {
        if (!start) return;
        const { it, moved } = start;
        start = null; it.node.classList.remove("is-dragging"); host.style.cursor = "";
        if (e.type === "pointercancel") return;
        if (!moved) return this.select(it.k);
        // Rescale only when something touches the top or the right edge.
        const wd = this.world(), b = Core.box(it, this.which);
        if (it.pos.y + b.h >= wd.h * 0.98 || it.pos.x + b.w >= wd.w * 0.98) this.fit();
        this.draw();
      };
      host.addEventListener("pointerup", end);
      host.addEventListener("pointercancel", end);
    }
    keys(node, it) {
      node.addEventListener("focus", () => { it.z = ++this.z; this.draw(); });
      node.addEventListener("keydown", (e) => {
        const st = Core.step(this.s) / (e.shiftKey ? 1 : 2);
        const d = { ArrowLeft: [-st, 0], ArrowRight: [st, 0], ArrowUp: [0, st], ArrowDown: [0, -st] }[e.key];
        if (d) { e.preventDefault(); this.move(it, it.pos.x + d[0], it.pos.y + d[1]); }
        else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.select(it.k); }
      });
    }
    select(k) { this.sel = this.sel === k ? null : k; this.draw(); this.opts.onSelect && this.opts.onSelect(this.sel); }
  }

  // ------------------------------------------------------------ details & picker
  function detail(it, onRemove) {
    const li = el("li", "cmp-item");
    li.dataset.k = it.k;
    const dot = el("span", "cmp-dot"); dot.style.background = it.color; li.append(dot);
    let name, size, meta, more = "";
    if (it.kind === "taxon") {
      name = `<a href="${esc(it.u)}">${label(it)}</a>`;
      size = `${Core.range(it.lo, it.hi, LANG)} ${esc(L.cmp_long)}`
        + (it.pr ? ` <span class="cmp-badge">${esc(L.cmp_partial)}</span>` : "")
        + (it.old ? ` <span class="cmp-badge">${esc(L.cmp_old)}</span>` : "");
      const sil = fill(L["cmp_sil_" + it.lv] || L.cmp_sil_clade, { node: esc(it.nd) });
      meta = esc(fill(L.cmp_height_approx, { h: Core.len(Core.box(it, "max").h, LANG) })) + "<br>"
        + `${sil} · ${esc(it.au || "PhyloPic")} · ${link(it.lu, it.li)} · ${link(it.pg, "PhyloPic")}`;
      more = `<details><summary>${esc(L.cmp_source)}</summary>`
        + (it.qt ? `<blockquote>«${esc(it.qt)}»</blockquote>` : "")
        + `<p>${link(it.su, it.st + " (Wikipedia)")}</p>`
        + (it.ne > 1 ? `<p>${esc(fill(L.cmp_estimates, { n: it.ne, lo: Core.len(it.sp[0], LANG), hi: Core.len(it.sp[1], LANG) }))}</p>` : "")
        + `<p>${link(ISSUES + "?title=" + encodeURIComponent((LANG === "es" ? "Tamaño: " : "Size: ") + it.n), L.cmp_error)}</p></details>`;
    } else {
      name = esc(it.n);
      size = `${Core.range(it.lo, it.hi, LANG)} ${esc(it.ax === "height" ? L.cmp_tall : L.cmp_long)}`;
      meta = `${esc(L.cmp_measure)}: ${esc(it.note)} · ${link(it.su, it.st)}<br>`
        + (it.pg ? `${esc(it.au || "PhyloPic")} · ${link(it.lu, it.li)} · ${link(it.pg, "PhyloPic")}` : esc(L.cmp_sil_own));
    }
    li.insertAdjacentHTML("beforeend", `<span class="cmp-item__name">${name}</span>`);
    const x = el("button", "cmp-x", esc(L.cmp_remove)); x.type = "button";
    x.setAttribute("aria-label", `${L.cmp_remove}: ${it.n}`);
    x.addEventListener("click", () => onRemove(it.k));
    li.append(x);
    li.insertAdjacentHTML("beforeend", `<span class="cmp-item__size">${size}</span><span class="cmp-item__meta">${meta}</span>${more}`);
    return li;
  }

  function picker(ctl) {
    const box = el("div", "cmp-picker");
    const tabs = el("div", "cmp-tabs"); tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", L.cmp_add);
    const records = el("div", "cmp-records");
    const search = el("input", "cmp-search"); search.type = "search";
    search.placeholder = L.cmp_search; search.setAttribute("aria-label", L.cmp_search);
    const list = el("ul", "cmp-options");
    const more = el("p", "cmp-more");
    let kind = "taxon";
    KINDS.forEach((k) => {
      const b = el("button", null, esc(L["cmp_kind_" + k])); b.type = "button"; b.setAttribute("role", "tab"); b.dataset.k = k;
      b.addEventListener("click", () => { kind = k; paint(); });
      tabs.append(b);
    });
    const option = (c, extra) => {
      const b = el("button", "cmp-opt"); b.type = "button";
      b.setAttribute("aria-pressed", String(ctl.keys.includes(c.k)));
      b.innerHTML = `<span class="cmp-opt__pic" style='${maskStyle(c.s)}'></span><span>${extra ? esc(extra) + "<br>" : ""}${label(c)}</span><span class="cmp-opt__size">${Core.range(c.lo, c.hi, LANG)}</span>`;
      b.addEventListener("click", () => ctl.toggle(c.k));
      return b;
    };
    // The longest and the smallest taxon the comparator can draw.
    // (A taxon known only from an old estimate does not hold a record.)
    const byLen = IX.taxa.filter((t) => !t.old).sort((a, b) => b.hi - a.hi);
    records.append(el("p", "cmp-h", esc(L.cmp_records)));
    const recs = [[L.cmp_longest, byLen[0]], [L.cmp_smallest, byLen[byLen.length - 1]]];
    function paint() {
      tabs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.k === kind)));
      records.hidden = search.hidden = kind !== "taxon";
      records.querySelectorAll(".cmp-opt").forEach((n) => n.remove());
      recs.forEach(([lab, t]) => records.append(option(CATALOG.get(t.k), lab)));
      const q = search.value.trim().toLowerCase();
      const all = [...CATALOG.values()].filter((c) => c.kind === kind && (!q || c.n.toLowerCase().includes(q)));
      const shown = kind === "taxon" ? all.slice(0, LIST_LIMIT) : all;
      list.innerHTML = "";
      shown.forEach((c) => { const li = el("li"); li.append(option(c)); list.append(li); });
      more.textContent = all.length > shown.length ? fill(L.cmp_more, { n: all.length - shown.length }) : (all.length ? "" : L.cmp_none);
    }
    search.addEventListener("input", paint);
    box.append(tabs, records, search, list, more);
    box.paint = paint;
    return box;
  }

  // ------------------------------------------------------------ the comparator
  function comparator(keys, { page = null, origin = null } = {}) {
    const root = page || el("dialog", "cmp");
    root.classList.add("cmp");
    root.setAttribute("aria-labelledby", "cmp-title");
    root.innerHTML = "";
    const head = el("div", "cmp-head");
    head.innerHTML = page ? `<h2 id="cmp-title" class="visually-hidden">${esc(L.cmp_title)}</h2><span class="cmp-spacer"></span>` : `<h2 id="cmp-title">${esc(L.cmp_title)}</h2>`;
    const seg = el("div", "cmp-seg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", L.cmp_sizes);
    [["min", L.cmp_min], ["max", L.cmp_max]].forEach(([k, l]) => { const b = el("button", null, esc(l)); b.type = "button"; b.dataset.k = k; seg.append(b); });
    const reset = el("button", "cmp-btn", esc(L.cmp_reset)); reset.type = "button";
    const share = el("button", "cmp-btn", esc(L.cmp_copy)); share.type = "button";
    const status = el("span", "cmp-status"); status.setAttribute("role", "status");
    head.append(seg, reset, share, status);
    if (!page) {
      const x = el("button", "cmp-btn cmp-close", "×"); x.type = "button"; x.setAttribute("aria-label", L.cmp_close); x.autofocus = true;
      x.addEventListener("click", () => root.close());
      head.append(x);
    }
    const body = el("div", "cmp-body");
    const rail = el("div", "cmp-rail");
    const main = el("div", "cmp-main");
    const stageHost = el("div");
    const strip = el("ul", "cmp-items cmp-strip");
    const warn = el("p", "cmp-warn");
    const first = keys.find((k) => CATALOG.get(k).kind === "taxon");
    warn.innerHTML = esc(L.cmp_warn) + (first ? ` (<a href="${esc(CATALOG.get(first).u)}#historial">${esc(L.cmp_history)}</a>)` : "") + ".";
    main.append(stageHost, strip);
    body.append(rail, main);
    root.append(head, body, warn);

    const ctl = {
      keys: keys.slice(),
      toggle(k) {
        const i = this.keys.indexOf(k);
        if (i >= 0) this.keys.splice(i, 1);
        else if (this.keys.length < MAX_ITEMS) this.keys.push(k);
        else return say(L.cmp_max_items);
        update(true);
      },
    };
    const stage = new Stage(stageHost, { onSelect: paintSel });
    const pick = picker(ctl);
    rail.append(el("p", "cmp-h", esc(L.cmp_add)), pick);
    let timer;
    function say(msg) { status.textContent = msg; clearTimeout(timer); timer = setTimeout(() => (status.textContent = ""), 2500); }
    function paintSel(k) {
      strip.querySelectorAll(".cmp-item").forEach((li) => {
        li.classList.toggle("is-selected", li.dataset.k === k);
        if (li.dataset.k === k) li.scrollIntoView({ block: "nearest", inline: "nearest", behavior: REDUCED ? "auto" : "smooth" });
      });
    }
    function update(keep) {
      stage.set(ctl.keys, keep);
      strip.innerHTML = "";
      stage.items.forEach((it) => strip.append(detail(it, (k) => ctl.toggle(k))));
      pick.paint();
      seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === stage.which)));
      history.replaceState(null, "", location.pathname + location.search + Core.hash(IX.hash, ctl.keys));
    }
    seg.addEventListener("click", (e) => { const k = e.target.dataset && e.target.dataset.k; if (!k) return; stage.which = k; stage.relayout(); update(true); });
    reset.addEventListener("click", () => { stage.relayout(); say(L.cmp_reset_done); });
    share.addEventListener("click", async () => { try { await navigator.clipboard.writeText(location.href); say(L.cmp_copied); } catch { say(location.hash); } });

    if (!page) {
      document.body.append(root);
      root.addEventListener("close", () => {
        history.replaceState(null, "", location.pathname + location.search);
        root.remove();
        if (origin) origin.focus();
      });
      root.addEventListener("click", (e) => { if (e.target === root) root.close(); }); // the backdrop
      root.showModal();
    }
    requestAnimationFrame(() => update(false));
    return root;
  }

  // ------------------------------------------------------------ card and page
  function card(node) {
    const url = node.dataset.compare, key = node.dataset.key;
    const cta = node.querySelector(".cmp-card__cta");
    // The preview: the taxon next to an average man, drawn with the same stage.
    const mini = node.querySelector(".cmp-mini");
    loadIndex(url).then(() => {
      if (!CATALOG.has(key)) return;
      new Stage(mini, { static: true }).set([key, "man"]);
    });
    const open = (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.button > 0) return; // a new tab: the page
      const a = e.target.closest("a");
      if (a && a !== cta && !a.hasAttribute("data-cmp-open")) return; // the source link
      e.preventDefault();
      loadIndex(url).then(() => { if (CATALOG.has(key)) comparator([key, "man"], { origin: cta }); });
    };
    node.addEventListener("click", open);
    // Opened from a shared link: "#comparar=…".
    const keys = Core.parseHash(location.hash);
    if (keys.length) loadIndex(url).then(() => { const k = keys.filter((x) => CATALOG.has(x)); if (k.length) comparator(k, { origin: cta }); });
  }

  function startPage(host) {
    loadIndex(host.dataset.compare).then(() => {
      const keys = Core.parseHash(location.hash).filter((k) => CATALOG.has(k));
      const first = IX.taxa.find((t) => t.k === "tyrannosaurus") || IX.taxa[0];
      comparator(keys.length ? keys : [first.k, "man", "elephant"].filter((k) => CATALOG.has(k)), { page: host });
    });
  }

  document.querySelectorAll(".cmp-card[data-compare]").forEach(card);
  const host = document.getElementById("cmp-page");
  if (host) startPage(host);
})();
