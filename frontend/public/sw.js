/**
 * Vocira ka service worker.
 *
 * Maqsad mehdood hai aur jaan bujh kar: app install ho sake aur
 * network jaane par ek maani-khez safha nazar aaye. Ye offline app
 * banane ki koshish NAHI hai - Vocira ka poora kaam (voice, ERP,
 * RAG) server par hota hai, to offline "kaam" karne ka koi matlab
 * hi nahi.
 *
 * KYA CACHE HOTA HAI
 *
 *   app ka khol (offline page, icons, manifest)  -  hamesha
 *   Next ke build assets (/_next/static/...)     -  jaise miltay jayen
 *
 * KYA CACHE NAHI HOTA - aur kyun
 *
 *   /api, /auth, /livekit  ye zinda data hai. Purana attendance ya
 *                          fees dikhana ghalat maloomat dene ke
 *                          barabar hai - us se behtar hai ke saaf
 *                          nakami dikhe.
 *
 *   HTML safhe            navigation hamesha network se. Purana
 *                          safha dikha kar user ko ye samajhna ke
 *                          sab theek hai, us se bura kuch nahi.
 */

const VERSION = "vocira-v1";
const SHELL = `${VERSION}-shell`;
const ASSETS = `${VERSION}-assets`;

const OFFLINE_URL = "/offline.html";

const SHELL_FILES = [
  OFFLINE_URL,
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/manifest.webmanifest",
];

// Ye raaste kabhi cache nahi hote
const LIVE_PATHS = ["/api/", "/auth/", "/livekit/", "/_next/webpack-hmr"];

const isLive = (url) =>
  LIVE_PATHS.some((p) => url.pathname.startsWith(p));


self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL);
      // addAll ek bhi file par fail ho to poora install girta hai,
      // is liye har file alag - ek icon na mile to bhi SW chale.
      await Promise.all(
        SHELL_FILES.map((file) =>
          cache.add(file).catch(() => {
            /* is file ke baghair bhi kaam chalega */
          })
        )
      );
      // Naya SW purane ka intezaar na kare
      await self.skipWaiting();
    })()
  );
});


self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Purane version ke caches hata dein, warna har deploy par
      // storage barhta jayega
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

  // Sirf GET. POST/PATCH waghera cache karna khatarnak hai.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Doosri site ki cheezein (CDN, fonts) - browser khud sambhale
  if (url.origin !== self.location.origin) return;

  if (isLive(url)) return;

  // ---- HTML safhe: network first, warna offline page ----
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
  // /_next/static/ ke naam mein hash hota hai, is liye purana
  // content milne ka koi khatra nahi - naam badal jata hai to
  // request hi nayi hoti hai.
  if (url.pathname.startsWith("/_next/static/") ||
      url.pathname.startsWith("/icons/")) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(ASSETS);
        const hit = await cache.match(request);
        if (hit) return hit;

        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      })()
    );
  }
});
