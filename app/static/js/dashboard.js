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

// Pop-up de rappel sanitaire : verifie periodiquement (toutes les
// `intervalMinutes` minutes, plus une premiere fois au chargement) si une
// tache du programme sanitaire (vaccin, traitement, alimentation) est en
// attente pour le lot de l'utilisateur, et affiche un pop-up bloquant tant
// qu'elle n'est pas traitee ou reportee.
function initSanitaryReminders(options) {
  var checkUrl = options.checkUrl;
  var intervalMs = (options.intervalMinutes || 10) * 60 * 1000;
  var modalEl = document.getElementById("sanitaryReminderModal");
  if (!modalEl || !window.bootstrap) {
    return;
  }
  var modal = new bootstrap.Modal(modalEl);
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.content : "";

  function checkReminder() {
    // Ne pas interrompre l'utilisateur s'il a deja le pop-up ouvert, ou s'il
    // est en train de remplir un formulaire de saisie.
    if (modalEl.classList.contains("show")) {
      return;
    }
    fetch(checkUrl, { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : { has_reminder: false }; })
      .then(function (data) {
        if (!data.has_reminder) {
          return;
        }
        document.getElementById("sanitaryReminderContext").textContent =
          "Lot " + data.batch_code + " (" + data.farm_name + ") - Jour " + data.day_number;
        document.getElementById("sanitaryReminderProduct").textContent = data.product_name;
        document.getElementById("sanitaryReminderNotes").textContent = data.notes || "";
        document.getElementById("sanitaryReminderRoadmapLink").href = data.roadmap_url;

        var doneBtn = document.getElementById("sanitaryReminderDoneBtn");
        doneBtn.onclick = function () {
          var formData = new FormData();
          formData.append("csrf_token", csrfToken);
          fetch(data.mark_done_url, { method: "POST", body: formData }).finally(function () {
            modal.hide();
          });
        };

        modal.show();
      })
      .catch(function () {
        // Silencieux : une panne reseau temporaire ne doit pas gener l'utilisateur.
      });
  }

  checkReminder();
  setInterval(checkReminder, intervalMs);
}
