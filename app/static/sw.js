/* Service worker Farm Control - portee minimale et prudente :
   - met en cache la coquille statique (CSS/JS/icones) pour un chargement
     instantane et un usage hors-ligne de l'interface ;
   - sert une page de repli propre ("/hors-ligne") quand une navigation
     echoue faute de reseau, plutot que l'ecran d'erreur du navigateur ;
   - ne met JAMAIS en cache les reponses de formulaires (POST) ni les pages
     de donnees dynamiques : la mise en file d'attente hors-ligne de la
     saisie quotidienne est geree separement par offline-queue.js (IndexedDB),
     pas par ce service worker.
*/
const CACHE_VERSION = "fc-shell-v1";
const APP_SHELL = [
  "/static/css/custom.css",
  "/static/js/dashboard.js",
  "/static/js/offline-queue.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/manifest.json",
  "/hors-ligne",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Ne jamais intercepter les envois de formulaires (POST) : ils sont geres
  // par offline-queue.js pour les pages qui en ont besoin, et doivent sinon
  // echouer normalement pour que le navigateur affiche l'erreur reseau.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/hors-ligne"))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
          return response;
        });
      })
    );
  }
  // Toutes les autres requetes GET (pages dynamiques, exports...) passent
  // directement au reseau, sans mise en cache : leur contenu depend du
  // tenant/de l'utilisateur et ne doit pas etre reutilise entre sessions.
});
