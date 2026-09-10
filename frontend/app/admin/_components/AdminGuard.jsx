"use client";

/**
 * The admin panel's front door.
 *
 * There was no guard at all before: the /admin URL opened for
 * anyone. No data came back (every admin endpoint on the backend
 * sits behind require_admin and returns 403 for a parent's token) -
 * but the panel's whole frame rendered, sidebar and headings
 * included, and the error message arrived some moments later.
 *
 * The role is now checked first:
 *
 *     no token        ->  /login
 *     role not admin  ->  /dashboard
 *     admin           ->  the panel
 *
 * IMPORTANT: this is manners, not a gate. Changing the role in
 * localStorage is easy - and gains nothing, because the data still
 * comes from the backend, which checks the token's role itself. All
 * this guard does is send someone in the wrong place somewhere
 * sensible, and avoid a pointless glimpse of the admin UI.
 */

import { useEffect, useState } from "react";
import { Loader2, ShieldAlert } from "lucide-react";
import { getAccessToken } from "@/lib/session";

export default function AdminGuard({ children }) {
  // "checking" -> not known yet, "allowed" -> admin, "denied" -> redirected
  const [state, setState] = useState("checking");

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      window.location.href = "/login";
      setState("denied");
      return;
    }

    // The role is stored at login. If an older session does not
    // have it, read it out of the token.
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
    <div className="grid min-h-screen place-items-center text-white">
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
 * Read the role out of the JWT - the same as on the login page.
 *
 * base64url has to be converted to base64; atob does not understand
 * base64url.
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
