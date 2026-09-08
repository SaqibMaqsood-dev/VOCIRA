"use client";

/**
 * "App install karein" wala card.
 *
 * Browser khud ek chhota sa banner dikhata hai jo aksar nazar hi
 * nahi aata. beforeinstallprompt ko rok kar hum apna card dikhate
 * hain, aur user ke haan kehne par browser wala asli dialog kholte
 * hain.
 *
 * TAMEEZ KE USOOL - ye is component ka asal kaam hain:
 *
 *   - foran nahi. 12 second ka intezaar, taake banda pehle safha
 *     dekh le. Kholte hi popup phenkna sab se bura tareeqa hai.
 *   - "Not now" dabaya to 14 din tak dobara nahi.
 *   - install ho gaya to phir kabhi nahi.
 *   - jo pehle se standalone mein chal raha hai use kabhi nahi.
 *
 * iOS ka apna maamla hai: Safari beforeinstallprompt support hi
 * nahi karta, wahan "Share -> Add to Home Screen" hi raasta hai.
 * Is liye iPhone par card wo tareeqa batata hai, button nahi dikhata.
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

  useEffect(() => {
    // Pehle se install ho kar chal raha hai
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
    // Safari beforeinstallprompt nahi bhejta, is liye wahan sirf
    // waqt ka intezaar kar ke hidayat dikha dete hain.
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
      // Phir kabhi na poochein
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

  if (!visible) return null;

  const install = async () => {
    if (!deferred) return;

    try {
      setBusy(true);
      await deferred.prompt();
      const { outcome } = await deferred.userChoice;

      // Mana kar diya to thora arsa khamosh rahein - agli baar
      // poochne ka koi faida nahi jab abhi mana kiya hai.
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
            Border pehle white/12 tha - gehre card par wo ek saaf
            safaid lakeer ban kar kinare ko kaat raha tha.

            Ab teen halki parton se kinara banta hai:
              border   bohat halka, sirf shakl batane ko
              inset    andar ki taraf ek baal barabar roshni - shishe
                       ka kinara aisa hi lagta hai
              shadow   gehri aur phaili hui, yehi card ko background
                       se alag karti hai (border nahi)
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

/** Kya abhi khamoshi ka waqt hai */
function snoozed() {
  try {
    const until = Number(localStorage.getItem(SNOOZE_KEY) || 0);
    return until > Date.now();
  } catch {
    // Private mode mein localStorage phenk sakta hai. Aise mein
    // poochna behtar hai - card band karna aasan hai.
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
    /* yaad na rahe to bhi chalega */
  }
}
