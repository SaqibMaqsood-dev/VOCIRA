"use client";

/**
 * Admin panel ka darwaza.
 *
 * Pehle koi guard nahi tha: /admin URL kisi ko bhi khul jata tha.
 * Data zaroor nahi milta (backend ke saare admin endpoints
 * require_admin ke peeche hain, parent ke token par 403 dete hain) -
 * magar panel ka poora dhaancha render ho jata tha, sidebar aur
 * headings samet, aur ghalti ka paighaam kuch der baad aata tha.
 *
 * Ab role pehle dekha jata hai:
 *
 *     token nahi        ->  /login
 *     role admin nahi   ->  /dashboard
 *     admin             ->  panel
 *
 * AHEM: ye rok nahi, sirf tameez hai. localStorage ka role badal
 * dena aasan hai - aur us se kuch nahi milta, kyunke data phir bhi
 * backend se aata hai jo token ka role khud jaanchta hai. Ye guard
 * sirf ye karta hai ke ghalat jagah aane wale ko saaf raasta mile,
 * aur admin UI ki bemani jhalak na dikhe.
 */

import { useEffect, useState } from "react";
import { Loader2, ShieldAlert } from "lucide-react";

export default function AdminGuard({ children }) {
  // "checking" -> abhi pata nahi, "allowed" -> admin, "denied" -> bhej diya
  const [state, setState] = useState("checking");

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      window.location.href = "/login";
      setState("denied");
      return;
    }

    // Role login ke waqt rakha jata hai. Purane session mein na ho
    // to token se nikal lete hain.
    let role = localStorage.getItem("role");

    if (!role) {
      role = readRoleFromToken(token);
      if (role) localStorage.setItem("role", role);
    }

    if (role !== "admin") {
      window.location.href = "/dashboard";
      setState("denied");
      return;
    }

    setState("allowed");
  }, []);

  if (state === "allowed") {
    return children;
  }

  return (
    <div className="grid min-h-screen place-items-center bg-[#05041c] text-white">
      <div className="flex items-center gap-3 text-sm text-white/70">
        {state === "checking" ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking access…
          </>
        ) : (
          <>
            <ShieldAlert className="h-4 w-4 text-amber-300" />
            Redirecting…
          </>
        )}
      </div>
    </div>
  );
}

/**
 * JWT se role padhein - login page jaisa hi.
 *
 * base64url ko base64 mein badalna parta hai; atob base64url nahi
 * samajhta.
 */
function readRoleFromToken(token) {
  try {
    const part = token.split(".")[1];
    if (!part) return null;

    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);

    return JSON.parse(atob(padded))?.role || null;
  } catch {
    return null;
  }
}
