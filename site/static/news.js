// News page filters (type, language, with a taxon page) and the home tabs "Studies |
// In the media". Without JavaScript every story and both lists are shown.
(function () {
  "use strict";
  var filters = document.querySelector(".nm-filters");
  if (filters) {
    var state = { cat: "", lang: "" };
    filters.hidden = false;
    filters.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      var group = b.closest("[data-filter]");
      group.querySelectorAll("button").forEach(function (x) { x.classList.toggle("is-on", x === b); });
      state[group.dataset.filter] = b.dataset.v;
      document.querySelectorAll(".nm-story").forEach(function (s) {
        s.hidden = !((!state.cat || s.dataset.cat === state.cat) &&
                     (!state.lang || s.dataset.lang.split(" ").indexOf(state.lang) >= 0));
      });
    });
  }
  var tabs = document.querySelector(".news-tabs");
  if (tabs) {
    var studies = document.getElementById("news-studies"), media = document.getElementById("news-media");
    tabs.hidden = false; media.hidden = true; media.classList.add("is-tab");
    tabs.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      tabs.querySelectorAll("button").forEach(function (x) {
        var on = x === b; x.classList.toggle("is-on", on); x.setAttribute("aria-selected", on);
      });
      var showMedia = b.getAttribute("aria-controls") === "news-media";
      media.hidden = !showMedia; studies.hidden = showMedia;
    });
  }
})();
