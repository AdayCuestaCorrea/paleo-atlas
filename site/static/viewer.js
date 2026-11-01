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
  var links = [], current = 0;

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
  }

  document.addEventListener("click", function (ev) {
    var a = ev.target.closest("[data-viewer]");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey) return; // new tab: Commons page
    ev.preventDefault();
    links = visible();
    show(links.indexOf(a));
    dialog.showModal();
  });
  dialog.querySelector(".viewer__prev").addEventListener("click", function () { show(current - 1); });
  dialog.querySelector(".viewer__next").addEventListener("click", function () { show(current + 1); });
  dialog.querySelector(".viewer__close").addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("click", function (ev) { if (ev.target === dialog) dialog.close(); });
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
