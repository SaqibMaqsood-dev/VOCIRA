"use client";

/**
 * Registers the service worker.
 *
 * In production only: in dev, Next's own assets change constantly
 * and caching makes old code stick around - hours go into working
 * out why a change is not showing up.
 *
 * Registration happens after load, not immediately. Registering
 * fetches files over the network itself, and competing with the
 * first page load only makes that page slower.
 */

import { useEffect } from "react";

export default function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;

    const register = () => {
      navigator.serviceWorker.register("/sw.js").catch((error) => {
        // If registration fails the app still works fine - only
        // install and the offline page are lost.
        console.warn("Service worker did not register:", error);
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
