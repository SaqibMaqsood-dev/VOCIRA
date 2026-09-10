"use client";

/**
 * The "install the app" card.
 *
 * The browser shows a small banner of its own that usually goes
 * unnoticed. We intercept beforeinstallprompt to show our own card,
 * and open the browser's real dialog when the user says yes.
 *
 * RULES OF GOOD MANNERS - these are the point of this component:
 *
 *   - not immediately. A 12 second wait, so the person can look at
 *     the page first. Throwing a popup up on open is the worst way
 *     to do this.
 *   - if "Not now" is pressed, do not ask again for 14 days.
 *   - once installed, never again.
 *   - never for someone already running it standalone.
 *
 * iOS is its own case: Safari does not support beforeinstallprompt
 * at all, and "Share -> Add to Home Screen" is the only route there.
 * So on iPhone the card explains that instead of showing a button.
 */

import { useEffect, useState } from "react";
import { Download, Share, Sparkles, X } from "lucide-react";

const SNOOZE_KEY = "vocira:install-snoozed-until";
const SNOOZE_DAYS = 14;
const DELAY_MS = 12000;

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);
  const [visible, setVisible] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [busy, setBusy] = useState(false);

  // The admin panel's incoming call card also sits in the bottom
  // right corner. Both landed in the same place and printed over
  // each other - and next to a ringing call, a suggestion to install
  // is worth nothing. So this hides itself during a call.
  const [callOnScreen, setCallOnScreen] = useState(false);

  useEffect(() => {
    const onCall = (event) => setCallOnScreen(Boolean(event.detail));
    window.addEventListener("vocira-call", onCall);
    return () => window.removeEventListener("vocira-call", onCall);
  }, []);

  useEffect(() => {
    // Already installed and running
    const standalone =
      window.matchMedia?.("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;

    if (standalone) return;

    if (snoozed()) return;

    const ios =
      /iphone|ipad|ipod/i.test(window.navigator.userAgent) &&
      !window.MSStream;

    setIsIOS(ios);

    // ---- iOS ----
    // Safari never fires beforeinstallprompt, so there we just wait
    // out the delay and show the instructions.
    if (ios) {
      const timer = setTimeout(() => setVisible(true), DELAY_MS);
      return () => clearTimeout(timer);
    }

    // ---- baqi sab ----
    let timer;

    const onPrompt = (event) => {
      // Browser ka apna mini-banner rok dein
      event.preventDefault();
      setDeferred(event);
      timer = setTimeout(() => setVisible(true), DELAY_MS);
    };

    const onInstalled = () => {
      setVisible(false);
      setDeferred(null);
      // Never ask again
      remember(365);
    };

    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!visible || callOnScreen) return null;

  const install = async () => {
    if (!deferred) return;

    try {
      setBusy(true);
      await deferred.prompt();
      const { outcome } = await deferred.userChoice;

      // Once declined, stay quiet for a while - there is no point
      // asking again right after being turned down.
      if (outcome === "dismissed") remember(SNOOZE_DAYS);

      setVisible(false);
      setDeferred(null);
    } catch {
      setVisible(false);
    } finally {
      setBusy(false);
    }
  };

  const dismiss = () => {
    remember(SNOOZE_DAYS);
    setVisible(false);
  };

  return (
    <div
      role="dialog"
      aria-label="Install Vocira"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex justify-center px-4 pb-4 sm:justify-end sm:px-6 sm:pb-6"
    >
      <div className="pointer-events-auto w-full max-w-sm animate-install-in">
        {/*
            The border was white/12 - on a dark card that became a
            hard white line cutting across the edge.

            The edge is now built from three faint layers:
              border   very light, just enough to give it shape
              inset    a hairline of light on the inside - this is
                       what the edge of glass looks like
              shadow   deep and spread out; this is what separates
                       the card from the background, not the border
        */}
        <div
          className="relative overflow-hidden rounded-2xl bg-[#0b0a2a]/94 p-4 backdrop-blur-2xl"
          style={{
            boxShadow: [
              "0 0 0 1px rgba(255,255,255,0.06)",
              "inset 0 1px 0 rgba(255,255,255,0.07)",
              "0 24px 70px -12px rgba(0,0,0,0.7)",
              "0 8px 24px -8px rgba(108,99,255,0.22)",
            ].join(", "),
          }}
        >
          {/* upar roshni ki patli lakeer */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/25 to-transparent"
          />
          {/* halka sa glow */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -right-12 -top-14 h-36 w-36 rounded-full bg-accent-primary/20 blur-3xl"
          />

          <button
            type="button"
            onClick={dismiss}
            aria-label="Not now"
            className="absolute right-2.5 top-2.5 rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-white/10 hover:text-white"
          >
            <X className="h-3.5 w-3.5" />
          </button>

          <div className="relative flex gap-3.5">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent-secondary to-accent-primary shadow-lg">
              <Sparkles className="h-5 w-5 text-[#05041c]" />
            </span>

            <div className="min-w-0 pr-5">
              <p className="text-sm font-semibold leading-tight text-white">
                Install Vocira
              </p>
              <p className="mt-1.5 text-xs leading-5 text-text-secondary">
                {isIOS
                  ? "Add Vocira to your Home Screen to open it like an app."
                  : "Keep Vocira one tap away — opens full screen, no browser bar."}
              </p>
            </div>
          </div>

          {isIOS ? (
            <div className="relative mt-3.5 flex items-center gap-2 rounded-xl bg-white/[0.05] px-3 py-2.5 text-[11px] leading-5 text-text-secondary shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]">
              <Share className="h-3.5 w-3.5 shrink-0 text-accent-secondary" />
              <span>
                Tap <span className="font-semibold text-white">Share</span>,
                then{" "}
                <span className="font-semibold text-white">
                  Add to Home Screen
                </span>
              </span>
            </div>
          ) : (
            <div className="relative mt-3.5 flex gap-2">
              <button
                type="button"
                onClick={dismiss}
                className="flex-1 rounded-xl bg-white/[0.05] px-3 py-2.5 text-xs font-semibold text-text-secondary shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)] transition-colors hover:bg-white/[0.1] hover:text-white"
              >
                Not now
              </button>
              <button
                type="button"
                onClick={install}
                disabled={busy}
                className="flex flex-[1.4] items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-accent-primary to-[#4f45d1] px-3 py-2.5 text-xs font-semibold text-white shadow-lg transition-transform hover:-translate-y-px disabled:opacity-60"
              >
                <Download className="h-3.5 w-3.5" />
                {busy ? "Opening…" : "Install"}
              </button>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}

/** Whether we are currently in the quiet period */
function snoozed() {
  try {
    const until = Number(localStorage.getItem(SNOOZE_KEY) || 0);
    return until > Date.now();
  } catch {
    // localStorage can throw in private mode. Asking is the better
    // failure there - the card is easy to dismiss.
    return false;
  }
}

function remember(days) {
  try {
    localStorage.setItem(
      SNOOZE_KEY,
      String(Date.now() + days * 24 * 60 * 60 * 1000)
    );
  } catch {
    /* it works fine even if this is not remembered */
  }
}
