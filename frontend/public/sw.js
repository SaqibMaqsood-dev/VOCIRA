/**
 * Vocira ka service worker.
 *
 * The scope is deliberately narrow: let the app install, and show
 * something meaningful when the network goes. This is NOT an attempt
 * to build an offline app - all of Vocira's work (voice, ERP, RAG)
 * happens on the server, so working "offline" means nothing here.
 *
 * WHAT IS CACHED
 *
 *   the app shell (offline page, icons, manifest)  -  always
 *   Next's build assets (/_next/static/...)        -  as they arrive
 *
 * WHAT IS NOT CACHED - and why
 *
 *   /api, /auth, /livekit  this is live data. Showing stale
 *                          attendance or fees is the same as giving
 *                          wrong information - a clear failure is
 *                          better than that.
 *
 *   HTML pages             navigation always goes to the network.
 *                          Showing a stale page and letting the user
 *                          believe everything is fine is the worst
 *                          outcome of all.
 */

const VERSION = "vocira-v2";
const SHELL = `${VERSION}-shell`;
const ASSETS = `${VERSION}-assets`;

const OFFLINE_URL = "/offline.html";

const SHELL_FILES = [
  OFFLINE_URL,
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/manifest.webmanifest",
];

// These paths are never cached
const LIVE_PATHS = ["/api/", "/auth/", "/livekit/", "/_next/webpack-hmr"];

const isLive = (url) =>
  LIVE_PATHS.some((p) => url.pathname.startsWith(p));


self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL);
      // addAll fails the whole install if a single file fails, so
      // each file goes separately - a missing icon must not stop the
      // service worker.
      await Promise.all(
        SHELL_FILES.map((file) =>
          cache.add(file).catch(() => {
            /* it still works without this one file */
          })
        )
      );
      // Do not make the new worker wait behind the old one
      await self.skipWaiting();
    })()
  );
});


self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Drop caches from older versions, or storage grows with
      // every deploy
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => !n.startsWith(VERSION))
          .map((n) => caches.delete(n))
      );
      await self.clients.claim();
    })()
  );
});


self.addEventListener("fetch", (event) => {
  const { request } = event;

  // GET only. Caching POST/PATCH and the like is dangerous.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Cross-origin resources (CDN, fonts) - let the browser handle them
  if (url.origin !== self.location.origin) return;

  if (isLive(url)) return;

  // ---- HTML pages: network first, else the offline page ----
  if (request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          return await fetch(request);
        } catch {
          const cache = await caches.open(SHELL);
          return (
            (await cache.match(OFFLINE_URL)) ||
            new Response("Offline", { status: 503 })
          );
        }
      })()
    );
    return;
  }

  // ---- build assets: cache first ----
  //
  // /_next/static/ names carry a hash, so there is no risk of
  // serving stale content - when the content changes the name does
  // too, and the request is simply a different one.
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/manifest.webmanifest"
  ) {
    event.respondWith(
      (async () => {
        // caches.match() searches every cache, not just ASSETS.
        //
        // This branch used to look only in ASSETS, while install
        // precaches the icons and the manifest into SHELL - so a
        // precached icon was never found, and the precache did
        // nothing at all. Offline, the icons resolved only if the
        // user had happened to load them online first.
        //
        // The manifest is matched here for the same reason: it is
        // precached, but a manifest request is not a navigation and
        // matched no branch, so the worker never served it.
        const hit = await caches.match(request);
        if (hit) return hit;

        const cache = await caches.open(ASSETS);

        try {
          const response = await fetch(request);

          // The write is handed to waitUntil rather than left
          // floating: the browser is free to stop the worker as soon
          // as respondWith settles, which could cut the put short and
          // leave the asset uncached. waitUntil keeps it alive until
          // the write finishes, and does not delay the response.
          if (response.ok) {
            event.waitUntil(cache.put(request, response.clone()));
          }

          return response;
        } catch {
          // Offline with nothing cached. Returning a real response
          // rather than rejecting keeps the failure legible - an
          // unhandled rejection inside respondWith surfaces as an
          // opaque network error instead.
          return new Response("", { status: 504, statusText: "Offline" });
        }
      })()
    );
  }
});
