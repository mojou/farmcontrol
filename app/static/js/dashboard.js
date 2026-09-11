// Toggle du menu lateral en affichage mobile.
document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.querySelector(".fc-sidebar-toggle");
  var sidebar = document.querySelector(".fc-sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("is-open");
    });
  }
});

// Trace les courbes de mortalite cumulee et de consommation d'aliment
// cumulee (paragraphe 4) a partir des donnees JSON fournies par le serveur.
function renderBatchCharts(canvasIds, series) {
  var mortalityCanvas = document.getElementById(canvasIds.mortality);
  var feedCanvas = document.getElementById(canvasIds.feed);

  if (mortalityCanvas && series.mortality && series.mortality.length) {
    new Chart(mortalityCanvas, {
      type: "line",
      data: {
        labels: series.mortality.map(function (p) { return "J" + p.day; }),
        datasets: [
          {
            label: "Mortalite cumulee",
            data: series.mortality.map(function (p) { return p.cumulative; }),
            borderColor: "#b3261e",
            backgroundColor: "rgba(179, 38, 30, 0.12)",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  if (feedCanvas && series.feed && series.feed.length) {
    new Chart(feedCanvas, {
      type: "line",
      data: {
        labels: series.feed.map(function (p) { return "J" + p.day; }),
        datasets: [
          {
            label: "Aliment consomme cumule (kg)",
            data: series.feed.map(function (p) { return p.cumulative; }),
            borderColor: "#2f5233",
            backgroundColor: "rgba(47, 82, 51, 0.12)",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }
}
