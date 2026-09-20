/* File d'attente hors-ligne pour la saisie quotidienne (paragraphe fiabilite
 * terrain) : si le reseau coupe pendant l'envoi d'un formulaire, la saisie
 * est gardee dans IndexedDB sur l'appareil et renvoyee automatiquement des
 * que la connexion revient - au lieu d'etre perdue.
 *
 * Usage : attachOfflineForm(formElement, "Aliment") sur chaque formulaire de
 * saisie a proteger. Independant du service worker (sw.js), qui ne gere que
 * la mise en cache des fichiers statiques.
 */
(function () {
  const DB_NAME = "fc_offline";
  const STORE_NAME = "pending_submissions";

  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function queueSubmission(url, formData, label) {
    const entries = [];
    for (const [key, value] of formData.entries()) entries.push([key, value]);
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).add({ url, entries, label, timestamp: Date.now() });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function getPending() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const req = tx.objectStore(STORE_NAME).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function removePending(id) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  function entriesToFormData(entries) {
    const fd = new FormData();
    for (const [key, value] of entries) fd.append(key, value);
    return fd;
  }

  // fetch() suit les redirections par defaut : si la session a expire,
  // Flask-Login redirige vers /auth/login qui repond 200 - un simple test
  // sur response.ok dirait donc a tort que la saisie a ete enregistree, en
  // silence, alors qu'elle a ete perdue. On detecte ce cas via l'URL finale.
  function isSessionExpired(response) {
    return response.url.indexOf("/auth/login") !== -1;
  }

  function updateBadge(count) {
    const badge = document.getElementById("fc-offline-badge");
    if (!badge) return;
    const label = badge.querySelector("span");
    if (count > 0) {
      if (label) label.textContent = count === 1 ? FC_I18N.offlineOne : FC_I18N.offlineMany.replace("%(count)s", count);
      badge.classList.remove("d-none");
    } else {
      badge.classList.add("d-none");
    }
  }

  async function refreshBadge() {
    try {
      const pending = await getPending();
      updateBadge(pending.length);
      return pending.length;
    } catch (e) {
      return 0;
    }
  }

  let flushing = false;
  async function flushQueue() {
    if (flushing || !navigator.onLine) return;
    flushing = true;
    try {
      const pending = await getPending();
      let sentAny = false;
      for (const item of pending) {
        try {
          const response = await fetch(item.url, { method: "POST", body: entriesToFormData(item.entries) });
          if (response.ok && !isSessionExpired(response)) {
            await removePending(item.id);
            sentAny = true;
          } else if (isSessionExpired(response)) {
            // Garde la saisie en attente : reessaiera une fois reconnecte,
            // apres que l'utilisateur se soit reconnecte dans un onglet.
            break;
          }
        } catch (e) {
          break; // toujours hors-ligne : on arrete, on reessaiera plus tard
        }
      }
      await refreshBadge();
      if (sentAny) window.location.reload();
    } finally {
      flushing = false;
    }
  }

  function attachOfflineForm(form, label) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const url = form.action;
      const formData = new FormData(form);
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        const response = await fetch(url, { method: "POST", body: formData });
        if (response.ok && !isSessionExpired(response)) {
          window.location.reload();
          return;
        }
        // Le serveur a repondu mais a refuse (session expiree, formulaire
        // invalide...) : ne pas faire semblant d'avoir reussi.
        alert(FC_I18N.serverRefused);
      } catch (e) {
        // Echec reseau (vraiment hors-ligne) : on garde la saisie localement.
        await queueSubmission(url, formData, label || "Saisie");
        await refreshBadge();
        alert(FC_I18N.savedOffline);
        form.reset();
        const modalEl = form.closest(".modal");
        if (modalEl && window.bootstrap) {
          const modal = window.bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  window.addEventListener("online", flushQueue);
  document.addEventListener("DOMContentLoaded", () => {
    refreshBadge();
    flushQueue();
  });

  window.FarmControlOffline = { attachOfflineForm, flushQueue, refreshBadge };
})();
