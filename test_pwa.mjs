/**
 * PWA test, driven through the Chrome DevTools Protocol.
 *
 * No new dependencies: it launches the installed Chrome with a
 * debugging port and talks to it over the WebSocket that Node 22+
 * provides globally.
 *
 * What it checks:
 *   - the service worker registers and reaches "activated"
 *   - the manifest parses and carries what makes a PWA installable
 *   - the app shell is precached (offline.html, icons, manifest)
 *   - with the network cut, a navigation still returns the offline
 *     page rather than the browser's error page
 *
 * Usage, from the repo root, with the frontend built:
 *
 *     cd frontend && npx next build && npx next start -p 3111
 *     node test_pwa.mjs http://127.0.0.1:3111 online
 *
 *     # then stop the server and, with it down:
 *     node test_pwa.mjs http://127.0.0.1:3111 offline
 *
 * The offline phase needs the server genuinely stopped. Emulating
 * offline over CDP is not enough: that applies to the page's target,
 * while the fetch that has to fail is the service worker's own.
 */

import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.argv[2] || "http://127.0.0.1:3111";
const PORT = 9333;

// "online"  - the server is up: register, precache, installability
// "offline" - the server has been stopped: the shell must still serve
//
// The two run as separate invocations sharing one profile directory,
// so the registration made in the first is still there for the
// second. Emulating offline over CDP is not enough: that applies to
// the page's target, while the fetch that has to fail is the service
// worker's own, on a target of its own.
const PHASE = process.argv[3] === "offline" ? "offline" : "online";

const CHROME =
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const pass = [];
const fail = [];

function check(name, ok, detail = "") {
  (ok ? pass : fail).push(name);
  const mark = ok ? "PASS" : "FAIL";
  console.log(`  ${mark}  ${name}${!ok && detail ? ` - ${detail}` : ""}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------
// A very small CDP client
// ---------------------------------------------------------------

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.waiting = new Map();
    this.events = [];
    this.ws.addEventListener("message", (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && this.waiting.has(msg.id)) {
        const { resolve, reject } = this.waiting.get(msg.id);
        this.waiting.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      } else if (msg.method) {
        this.events.push(msg);
      }
    });
  }

  ready() {
    return new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
  }

  send(method, params = {}, sessionId) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.waiting.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params, sessionId }));
    });
  }

  close() {
    try {
      this.ws.close();
    } catch {
      /* already gone */
    }
  }
}

async function evaluate(cdp, session, expression) {
  const { result, exceptionDetails } = await cdp.send(
    "Runtime.evaluate",
    { expression, awaitPromise: true, returnByValue: true },
    session
  );
  if (exceptionDetails) {
    throw new Error(exceptionDetails.text || "evaluate failed");
  }
  return result.value;
}

// ---------------------------------------------------------------

async function main() {
  const profile = join(tmpdir(), "vocira-pwa-profile");
  mkdirSync(profile, { recursive: true });

  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-gpu",
    ],
    { stdio: "ignore" }
  );

  let cdp;

  try {
    // Wait for the debugging endpoint.
    let wsUrl = null;
    for (let i = 0; i < 40; i++) {
      try {
        const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
        wsUrl = (await res.json()).webSocketDebuggerUrl;
        if (wsUrl) break;
      } catch {
        /* not up yet */
      }
      await sleep(250);
    }

    if (!wsUrl) throw new Error("Chrome's debugging port never opened");

    cdp = new CDP(wsUrl);
    await cdp.ready();

    const { targetId } = await cdp.send("Target.createTarget", {
      url: "about:blank",
    });
    const { sessionId } = await cdp.send("Target.attachToTarget", {
      targetId,
      flatten: true,
    });

    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Runtime.enable", {}, sessionId);
    await cdp.send("Network.enable", {}, sessionId);

    // -----------------------------------------------------------
    console.log("\nservice worker");
    // -----------------------------------------------------------

    await cdp.send("Page.navigate", { url: `${BASE}/assistant` }, sessionId);
    await sleep(3500);

    const sw = await evaluate(
      cdp,
      sessionId,
      `(async () => {
         if (!('serviceWorker' in navigator)) return { supported: false };
         const reg = await navigator.serviceWorker.getRegistration();
         if (!reg) return { supported: true, registered: false };
         const w = reg.active || reg.installing || reg.waiting;
         return {
           supported: true,
           registered: true,
           scope: reg.scope,
           state: w ? w.state : null,
           script: w ? w.scriptURL : null,
         };
       })()`
    );

    check("registers", sw.registered === true, JSON.stringify(sw));
    check("script is /sw.js", (sw.script || "").endsWith("/sw.js"), sw.script);
    check("scope is the whole origin", (sw.scope || "").endsWith("/"), sw.scope);

    // Give it a moment to finish activating.
    for (let i = 0; i < 20 && sw.state !== "activated"; i++) {
      await sleep(300);
      const again = await evaluate(
        cdp,
        sessionId,
        `(async () => {
           const reg = await navigator.serviceWorker.getRegistration();
           const w = reg && (reg.active || reg.installing || reg.waiting);
           return w ? w.state : null;
         })()`
      );
      sw.state = again;
    }
    check("reaches activated", sw.state === "activated", `state=${sw.state}`);

    if (PHASE === "online") {
    // -----------------------------------------------------------
    console.log("\nprecached shell");
    // -----------------------------------------------------------

    const cached = await evaluate(
      cdp,
      sessionId,
      `(async () => {
         const names = await caches.keys();
         const out = { names, shell: [] };
         for (const n of names) {
           const c = await caches.open(n);
           const keys = await c.keys();
           out.shell.push(...keys.map((r) => new URL(r.url).pathname));
         }
         return out;
       })()`
    );

    check("a cache was opened", cached.names.length > 0, JSON.stringify(cached.names));
    for (const file of [
      "/offline.html",
      "/icons/icon-192.png",
      "/icons/icon-512.png",
      "/manifest.webmanifest",
    ]) {
      check(`precached ${file}`, cached.shell.includes(file));
    }

    // -----------------------------------------------------------
    console.log("\ninstallability");
    // -----------------------------------------------------------

    const manifest = await evaluate(
      cdp,
      sessionId,
      `(async () => {
         const link = document.querySelector('link[rel="manifest"]');
         if (!link) return null;
         const res = await fetch(link.href);
         return await res.json();
       })()`
    );

    check("manifest is linked and parses", manifest !== null);
    if (manifest) {
      check("has name", Boolean(manifest.name));
      check("has short_name", Boolean(manifest.short_name));
      check("has start_url", Boolean(manifest.start_url));
      check(
        "display is standalone",
        ["standalone", "fullscreen", "minimal-ui"].includes(manifest.display),
        manifest.display
      );
      const sizes = (manifest.icons || []).map((i) => i.sizes);
      check("has a 192px icon", sizes.includes("192x192"));
      check("has a 512px icon", sizes.includes("512x512"));
      check(
        "has a maskable icon",
        (manifest.icons || []).some((i) => (i.purpose || "").includes("maskable"))
      );
    }

    const appleCapable = await evaluate(
      cdp,
      sessionId,
      `Boolean(document.querySelector('meta[name="apple-mobile-web-app-capable"]'))`
    );
    check("declares apple-mobile-web-app-capable (older iOS)", appleCapable === true);

    }

    if (PHASE === "offline") {
      // ---------------------------------------------------------
      console.log();
      console.log("offline (the server is genuinely stopped)");
      // ---------------------------------------------------------

      // The navigation above already went through the worker: this
      // phase runs with the server down, so its fetch had to fail.
      const offline = await evaluate(
        cdp,
        sessionId,
        `({
           title: document.title,
           text: (document.body ? document.body.innerText : "").slice(0, 300),
           heading: (document.querySelector("h1, h2") || {}).innerText || "",
         })`
      );

      const served =
        /offline/i.test(offline.title) ||
        /offline/i.test(offline.heading) ||
        /offline|no connection|reconnect/i.test(offline.text);

      check(
        "a navigation with the server down serves the offline page",
        served,
        `title=${JSON.stringify(offline.title)} heading=${JSON.stringify(offline.heading)}`
      );

      check(
        "it is our page, not the browser's error page",
        !/ERR_|can.t be reached|took too long/i.test(offline.text),
        offline.text.slice(0, 120)
      );

      const icon = await evaluate(
        cdp,
        sessionId,
        `(async () => {
           try {
             const r = await fetch("/icons/icon-192.png");
             return r.ok;
           } catch { return false; }
         })()`
      );
      check("a precached icon is still served offline", icon === true);
    }
  } finally {
    cdp?.close();
    chrome.kill();
    await sleep(400);
  }

  console.log("\n" + "=".repeat(52));
  console.log(`passed ${pass.length}, failed ${fail.length}`);
  for (const f of fail) console.log(`  FAILED  ${f}`);
  console.log("=".repeat(52));

  process.exit(fail.length ? 1 : 0);
}

main().catch((e) => {
  console.error("test harness error:", e.message);
  process.exit(2);
});
