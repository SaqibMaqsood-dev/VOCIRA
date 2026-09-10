/**
 * Real browser end-to-end test of the login + session flow, driven
 * through the Chrome DevTools Protocol (same approach as test_pwa.mjs).
 *
 * Exercises:
 *   1. the actual /login page -> localStorage gets access_token AND
 *      refresh_token (this used to be impossible - login never
 *      returned a refresh token)
 *   2. the stored access token is accepted by a real API call
 *   3. tampering with the stored access token so the next API call
 *      is guaranteed to 401, then loading /dashboard - which goes
 *      through authFetch() - and confirming the token gets silently
 *      replaced and the page still works. This is the real renew-and-
 *      retry code path running in a live browser, not a unit test.
 *
 * Usage, with the auth, gateway and livekit_rag services running
 * locally (ports 8000/9000/8001) and the frontend built and started:
 *
 *     node test_login_e2e.mjs <base-url> <test-email> <test-password> [api-url]
 *
 * The test user must already exist (see the signup call in the
 * project notes) - this script only exercises login/refresh, it does
 * not create or delete accounts.
 */

import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.argv[2] || "http://127.0.0.1:3111";
const EMAIL = process.argv[3];
const PASSWORD = process.argv[4];
const API_URL = process.argv[5] || "http://127.0.0.1:9000";
const PORT = 9334;
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

if (!EMAIL || !PASSWORD) {
  console.error("usage: node login_e2e_test.mjs <base-url> <email> <password> [api-url]");
  process.exit(2);
}

const pass = [];
const fail = [];
function check(name, ok, detail = "") {
  (ok ? pass : fail).push(name);
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${!ok && detail ? ` - ${detail}` : ""}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.waiting = new Map();
    this.ws.addEventListener("message", (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && this.waiting.has(msg.id)) {
        const { resolve, reject } = this.waiting.get(msg.id);
        this.waiting.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
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

async function main() {
  const profile = join(tmpdir(), "vocira-login-e2e-profile");
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

    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Runtime.enable", {}, sessionId);

    // -----------------------------------------------------------
    console.log("\nlogin page");
    // -----------------------------------------------------------

    await cdp.send("Page.navigate", { url: `${BASE}/login` }, sessionId);
    await sleep(1500);

    const loginResult = await evaluate(
      cdp,
      sessionId,
      `(async () => {
         const email = document.querySelector('input#username, input[name="username"], input[type="email"]');
         const password = document.querySelector('input[type="password"]');
         const form = document.querySelector('form');
         if (!email || !password || !form) {
           return {
             ok: false,
             hasEmail: Boolean(email),
             hasPassword: Boolean(password),
             hasForm: Boolean(form),
           };
         }
         const setValue = (el, value) => {
           const proto = Object.getPrototypeOf(el);
           const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
           setter.call(el, value);
           el.dispatchEvent(new Event("input", { bubbles: true }));
         };
         setValue(email, ${JSON.stringify(EMAIL)});
         setValue(password, ${JSON.stringify(PASSWORD)});
         form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
         return { ok: true };
       })()`
    );
    check("found the login form and submitted it", loginResult.ok === true, JSON.stringify(loginResult));

    // Give the fetch and redirect time to complete.
    await sleep(2500);

    const stored = await evaluate(
      cdp,
      sessionId,
      `({
         access: localStorage.getItem("access_token"),
         refresh: localStorage.getItem("refresh_token"),
         url: location.pathname,
       })`
    );

    check("access_token was stored", Boolean(stored.access), JSON.stringify(stored));
    check(
      "refresh_token was stored (this used to never happen)",
      Boolean(stored.refresh),
      JSON.stringify(stored)
    );
    check("navigated away from /login on success", stored.url !== "/login", `stayed on ${stored.url}`);

    // -----------------------------------------------------------
    console.log("\nauthenticated request");
    // -----------------------------------------------------------

    const apiCheck = await evaluate(
      cdp,
      sessionId,
      `(async () => {
         const token = localStorage.getItem("access_token");
         const res = await fetch(${JSON.stringify(API_URL)} + "/auth/users/", {
           headers: { Authorization: "Bearer " + token },
         });
         return { status: res.status, ok: res.ok };
       })()`
    );
    check("stored access token is accepted by the API", apiCheck.ok === true, JSON.stringify(apiCheck));

    // -----------------------------------------------------------
    console.log("\nauto-renew on a bad access token");
    // -----------------------------------------------------------

    // Guarantee the next authFetch() call gets a 401, then load a
    // page that calls it (the dashboard reads sessions/stats through
    // authFetch). If renewal works, the tampered suffix is gone from
    // the stored token afterwards and the page still has data.
    await evaluate(
      cdp,
      sessionId,
      `(() => {
         const original = localStorage.getItem("access_token");
         localStorage.setItem("access_token", original + "tampered");
       })()`
    );

    await cdp.send("Page.navigate", { url: `${BASE}/dashboard` }, sessionId);
    await sleep(2500);

    const afterTamper = await evaluate(
      cdp,
      sessionId,
      `({
         url: location.pathname,
         access: localStorage.getItem("access_token") || "",
       })`
    );

    check(
      "a bad access token is silently renewed (the tampered suffix is gone)",
      Boolean(afterTamper.access) && !afterTamper.access.endsWith("tampered"),
      JSON.stringify({ url: afterTamper.url, endsTampered: afterTamper.access.endsWith("tampered") })
    );
    check("the app did not bounce to /login over it", afterTamper.url === "/dashboard", afterTamper.url);
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
