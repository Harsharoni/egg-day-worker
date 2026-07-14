(function () {
  "use strict";

  /* ---- tooltips --------------------------------------------------- */
  var tip = document.createElement("div");
  tip.className = "js-tooltip";
  document.body.appendChild(tip);

  var MARGIN = 8; /* px gap between element edge and tooltip */

  function showTip(el) {
    tip.textContent = el.getAttribute("data-tooltip");
    tip.style.left = "-9999px"; /* measure off-screen first */
    tip.style.top = "-9999px";
    tip.classList.add("visible");

    var r = el.getBoundingClientRect();
    var tw = tip.offsetWidth;
    var th = tip.offsetHeight;

    /* centre above the element; clamp so it stays in-viewport */
    var left = r.left + r.width / 2 - tw / 2;
    left = Math.max(MARGIN, Math.min(left, window.innerWidth - tw - MARGIN));

    var top = r.top - th - MARGIN;
    if (top < MARGIN) top = r.bottom + MARGIN; /* flip below if no room */

    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  function hideTip() {
    tip.classList.remove("visible");
  }

  document.querySelectorAll("[data-tooltip]").forEach(function (el) {
    el.addEventListener("mouseenter", function () { showTip(el); });
    el.addEventListener("mouseleave", hideTip);
    el.addEventListener("focus", function () { showTip(el); });
    el.addEventListener("blur", hideTip);
  });

  /* ---- countdown -------------------------------------------------- */
  var cd = document.getElementById("countdown");
  if (cd) {
    var startMs = Number(cd.dataset.startEpoch) * 1000;
    var endMs = Number(cd.dataset.endEpoch) * 1000;

    var pad = function (n) { return String(n).padStart(2, "0"); };
    var fmt = function (ms) {
      var s = Math.max(0, Math.floor(ms / 1000));
      var d = Math.floor(s / 86400);
      var h = Math.floor((s % 86400) / 3600);
      var m = Math.floor((s % 3600) / 60);
      return (d ? d + "d " : "") + pad(h) + ":" + pad(m) + ":" + pad(s % 60);
    };
    var tick = function () {
      var now = Date.now();
      if (now < startMs) {
        cd.textContent = "Starts in " + fmt(startMs - now);
      } else if (now < endMs) {
        cd.textContent = "Ends in " + fmt(endMs - now);
      } else {
        cd.textContent = "Competition over";
        return;
      }
      setTimeout(tick, 1000);
    };
    tick();
  }

  /* ---- charts ------------------------------------------------------ */
  if (typeof Chart !== "undefined") {
    var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    /* categorical slots in fixed order (identity follows the entity) */
    var PALETTE = dark
      ? ["#3987e5", "#199e70", "#c98500", "#008300",
        "#9085e9", "#e66767", "#d55181", "#d95926"]
      : ["#2a78d6", "#1baf7a", "#eda100", "#008300",
        "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"];
    var css = getComputedStyle(document.documentElement);
    var GRID = css.getPropertyValue("--grid").trim();
    var MUTED = css.getPropertyValue("--muted").trim();
    var INK2 = css.getPropertyValue("--ink-2").trim();

    var MAG = [
      [1e63, "V"], [1e60, "Nd"], [1e57, "Od"], [1e54, "Sd"], [1e51, "sd"],
      [1e48, "Qd"], [1e45, "qd"], [1e42, "Td"], [1e39, "D"], [1e36, "U"],
      [1e33, "d"], [1e30, "N"], [1e27, "o"], [1e24, "S"], [1e21, "s"],
      [1e18, "Q"], [1e15, "q"], [1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"],
    ];
    var fmtMag = function (v) {
      var a = Math.abs(v);
      for (var i = 0; i < MAG.length; i++) {
        if (a >= MAG[i][0]) return (v / MAG[i][0]).toFixed(2) + MAG[i][1];
      }
      return Number(v).toLocaleString();
    };
    var fmtPlain = function (v) { return Number(v).toLocaleString(); };

    document.querySelectorAll("canvas[data-series]").forEach(function (canvas) {
      var payload = JSON.parse(
        document.getElementById(canvas.dataset.series).textContent
      );
      var kind = canvas.dataset.kind; /* mag | plain | rank */
      var field = canvas.dataset.field;
      var fmtVal = kind === "mag" ? fmtMag : fmtPlain;

      /* single metric → one dataset; field="datasets" → one per guild.
         Palette has 8 fixed slots; never cycle — beyond 8 falls off. */
      var raw = field === "datasets"
        ? payload.datasets.slice(0, PALETTE.length)
        : [{ label: canvas.dataset.label || "", data: payload[field] }];

      var datasets = raw.map(function (d, i) {
        return {
          label: d.label,
          data: d.data,
          borderColor: PALETTE[i],
          backgroundColor: PALETTE[i],
          borderWidth: 2,
          pointRadius: 0,
          pointHitRadius: 12,
          tension: 0.15,
        };
      });

      new Chart(canvas, {
        type: "line",
        data: { labels: payload.labels, datasets: datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          hover: { mode: "index", intersect: false },
          plugins: {
            /* single series: the box title names it, no legend */
            legend: {
              display: datasets.length > 1,
              labels: { color: INK2, boxWidth: 12, boxHeight: 12 },
            },
            tooltip: {
              intersect: false,
              mode: "index",
              callbacks: {
                label: function (item) {
                  var name = item.dataset.label ? item.dataset.label + ": " : "";
                  return kind === "rank"
                    ? name + "Rank " + item.parsed.y
                    : name + fmtVal(item.parsed.y);
                },
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: MUTED, maxTicksLimit: 8, maxRotation: 0 },
            },
            y: {
              reverse: kind === "rank", /* rank 1 belongs on top */
              min: kind === "rank" ? 1 : undefined, /* no rank below 1 — grace pads past it otherwise */
              grace: "5%",
              grid: { color: GRID },
              ticks: {
                color: MUTED,
                callback: function (v) {
                  return kind === "rank" ? v : fmtVal(v);
                },
              },
            },
          },
        },
      });
    });
  }

  /* ---- leaderboard search ------------------------------------------ */
  var search = document.getElementById("player-search");
  if (search) {
    var rows = document.querySelectorAll("#leaderboard-table tbody tr");
    var empty = document.getElementById("search-empty");
    var emptyTerm = empty ? empty.querySelector("span") : null;

    search.addEventListener("input", function () {
      var term = search.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {
        var match = !term || row.dataset.search.indexOf(term) !== -1;
        row.hidden = !match;
        if (match) shown++;
      });
      if (empty) {
        empty.hidden = shown !== 0;
        if (emptyTerm) emptyTerm.textContent = search.value.trim();
      }
    });
  }

  /* ---- leaderboard sort --------------------------------------------- */
  var sortTable = document.getElementById("leaderboard-table");
  if (sortTable) {
    var tbody = sortTable.querySelector("tbody");
    var headers = sortTable.querySelectorAll("th.sortable");
    var activeTh = sortTable.querySelector("th.sort-desc, th.sort-asc");
    var activeDir = activeTh && activeTh.classList.contains("sort-asc") ? "asc" : "desc";

    var attrName = function (key) {
      return "data-" + key.replace(/[A-Z]/g, function (c) { return "-" + c.toLowerCase(); });
    };

    var sortBy = function (th) {
      var key = th.dataset.sortKey;
      var isText = th.dataset.sortType === "text";
      var dir = th === activeTh && activeDir === "desc" ? "asc" : "desc";

      headers.forEach(function (h) { h.classList.remove("sort-asc", "sort-desc"); });
      th.classList.add(dir === "asc" ? "sort-asc" : "sort-desc");
      activeTh = th;
      activeDir = dir;

      var attr = attrName(key);
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var av = a.getAttribute(attr);
        var bv = b.getAttribute(attr);
        var missA = av === null || av === "";
        var missB = bv === null || bv === "";
        if (missA && missB) return 0;
        if (missA) return 1; /* missing values always sink to the bottom */
        if (missB) return -1;
        if (isText) {
          return dir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
        }
        var na = parseFloat(av);
        var nb = parseFloat(bv);
        return dir === "asc" ? na - nb : nb - na;
      });
      rows.forEach(function (row) { tbody.appendChild(row); });
    };

    headers.forEach(function (th) {
      th.addEventListener("click", function () { sortBy(th); });
    });
  }

  /* ---- gentle auto-refresh while the comp is live ------------------ */
  if (document.body.dataset.phase === "live") {
    setTimeout(function () { location.reload(); }, 120000);
  }

  /* ---- manual refresh button ---------------------------------------- */
  var refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () { location.reload(); });
  }
})();
