// Image viewer for taxon pages: a native <dialog> with the large image, its
// credit and license; arrows and keyboard move through the gallery. Without
// JavaScript every image simply links to its page on Commons.
(function () {
  "use strict";
  var dialog = document.querySelector("dialog.viewer");
  if (!dialog || typeof dialog.showModal !== "function") return;
  var img = dialog.querySelector("img");
  var caption = dialog.querySelector(".viewer__caption");
  var license = dialog.querySelector(".viewer__license");
  var source = dialog.querySelector(".viewer__source");
  var strip = dialog.querySelector(".viewer__strip");
  var links = [], current = 0;

  // The viewer's own strip of thumbnails: one per picture, the current one marked.
  function buildStrip() {
    strip.textContent = "";
    strip.hidden = links.length < 2;
    links.forEach(function (a, i) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "viewer__thumb";
      b.setAttribute("aria-label", a.getAttribute("aria-label") || String(i + 1));
      var t = document.createElement("img");
      t.src = a.dataset.thumb || a.dataset.full;
      t.alt = "";
      b.appendChild(t);
      b.addEventListener("click", function () { show(i); });
      strip.appendChild(b);
    });
  }

  function visible() {
    return Array.prototype.filter.call(document.querySelectorAll("[data-viewer]"), function (a) {
      return !a.closest("[hidden]");
    });
  }
  function show(i) {
    current = (i + links.length) % links.length;
    var a = links[current];
    img.src = a.dataset.full;
    img.alt = a.getAttribute("aria-label") || "";
    caption.textContent = a.dataset.caption;
    license.hidden = !a.dataset.licenseUrl;
    license.href = a.dataset.licenseUrl || "#";
    source.href = a.href;
    var single = links.length < 2;
    dialog.querySelector(".viewer__prev").hidden = single;
    dialog.querySelector(".viewer__next").hidden = single;
    Array.prototype.forEach.call(strip.children, function (b, i) {
      var on = i === current;
      b.classList.toggle("is-current", on);
      b.setAttribute("aria-current", on ? "true" : "false");
      if (on) b.scrollIntoView({ block: "nearest", inline: "center" });
    });
  }

  function open(list, i) {
    links = list;
    buildStrip();
    dialog.showModal();
    show(i);
  }

  document.addEventListener("click", function (ev) {
    if (ev.ctrlKey || ev.metaKey || ev.shiftKey) return; // new tab: Commons page
    // A thumbnail under the main picture: every picture, from that one.
    var thumb = ev.target.closest("[data-open]");
    if (thumb) {
      ev.preventDefault();
      open(Array.prototype.slice.call(document.querySelectorAll("[data-viewer]")),
           parseInt(thumb.dataset.open, 10) || 0);
      return;
    }
    var a = ev.target.closest("[data-viewer]");
    if (!a) return;
    ev.preventDefault();
    var list = visible();
    open(list, list.indexOf(a));
  });
  dialog.querySelector(".viewer__prev").addEventListener("click", function () { show(current - 1); });
  dialog.querySelector(".viewer__next").addEventListener("click", function () { show(current + 1); });
  dialog.querySelector(".viewer__close").addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("click", function (ev) { if (ev.target === dialog) dialog.close(); });
  // A click on the left or right third of the picture moves too.
  img.addEventListener("click", function (ev) {
    if (links.length < 2) return;
    var box = img.getBoundingClientRect();
    var x = (ev.clientX - box.left) / box.width;
    if (x < 1 / 3) show(current - 1);
    else if (x > 2 / 3) show(current + 1);
  });
  dialog.addEventListener("keydown", function (ev) {
    if (ev.key === "ArrowLeft") show(current - 1);
    if (ev.key === "ArrowRight") show(current + 1);
  });
  dialog.addEventListener("close", function () { img.removeAttribute("src"); });

  // Swipe on touch screens.
  var startX = null;
  dialog.addEventListener("touchstart", function (ev) { startX = ev.touches[0].clientX; }, { passive: true });
  dialog.addEventListener("touchend", function (ev) {
    if (startX === null) return;
    var dx = ev.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 50) show(current + (dx < 0 ? 1 : -1));
    startX = null;
  });

  // Gallery filters by kind.
  document.querySelectorAll(".gallery__filters .chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var kind = chip.dataset.kind;
      document.querySelectorAll(".gallery__filters .chip").forEach(function (c) {
        var on = c === chip;
        c.classList.toggle("chip--on", on);
        c.setAttribute("aria-pressed", on ? "true" : "false");
      });
      document.querySelectorAll(".gallery__item").forEach(function (item) {
        item.hidden = Boolean(kind) && item.dataset.kind !== kind;
      });
    });
  });
})();
