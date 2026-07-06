(function () {
  "use strict";

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
    var css = getComputedStyle(document.documentElement);
    var ACCENT = css.getPropertyValue("--accent").trim();
    var GRID = css.getPropertyValue("--grid").trim();
    var MUTED = css.getPropertyValue("--muted").trim();

    var MAG = [
      [1e33, "d"], [1e30, "N"], [1e27, "o"], [1e24, "S"], [1e21, "s"],
      [1e18, "Q"], [1e15, "q"], [1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"],
    ];
    var fmtMag = function (v) {
      var a = Math.abs(v);
      for (var i = 0; i < MAG.length; i++) {
        if (a >= MAG[i][0]) return (v / MAG[i][0]).toFixed(2) + MAG[i][1];
      }
      return String(v);
    };

    document.querySelectorAll("canvas[data-series]").forEach(function (canvas) {
      var payload = JSON.parse(
        document.getElementById(canvas.dataset.series).textContent
      );
      var isRank = canvas.dataset.kind === "rank";
      var data = isRank ? payload.rank : payload.soul_eggs;

      new Chart(canvas, {
        type: "line",
        data: {
          labels: payload.labels,
          datasets: [{
            data: data,
            borderColor: ACCENT,
            backgroundColor: ACCENT,
            borderWidth: 2,
            pointRadius: 0,
            pointHitRadius: 12,
            tension: 0.15,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },  /* single series: title names it */
            tooltip: {
              intersect: false,
              mode: "index",
              callbacks: {
                label: function (item) {
                  return isRank ? "Rank " + item.parsed.y : fmtMag(item.parsed.y);
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
              reverse: isRank,          /* rank 1 belongs on top */
              grace: "5%",
              grid: { color: GRID },
              ticks: {
                color: MUTED,
                callback: function (v) {
                  return isRank ? v : fmtMag(v);
                },
              },
            },
          },
        },
      });
    });
  }

  /* ---- gentle auto-refresh while the comp is live ------------------ */
  if (document.body.dataset.phase === "live") {
    setTimeout(function () { location.reload(); }, 120000);
  }
})();
