"use client";

/**
 * Service worker register karta hai.
 *
 * Sirf production mein: dev mein Next ke apne assets har baar badalte
 * hain aur cache karne se purana code chipak jata hai - ghante barbad
 * hote hain ye samajhne mein ke tabdeeli kyun nazar nahi aa rahi.
 *
 * load ke baad register karte hain, foran nahi. Register karna khud
 * network se files mangwata hai, aur wo pehle safhe ke saath muqabla
 * kare to safha der se khulta hai.
 */

import { useEffect } from "react";

export default function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;

    const register = () => {
      navigator.serviceWorker.register("/sw.js").catch((error) => {
        // Register na ho to app phir bhi theek chalti hai - bas
        // install aur offline page nahi milega.
        console.warn("Service worker register nahi hua:", error);
      });
    };

    if (document.readyState === "complete") {
      register();
    } else {
      window.addEventListener("load", register);
      return () => window.removeEventListener("load", register);
    }
  }, []);

  return null;
}
