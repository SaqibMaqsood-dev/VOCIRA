"use client";

/**
 * Admin panel ka header.
 *
 * Pehle yahan chaar cheezein sirf dikhawa thin:
 *
 *   "AD" / "Admin"   hardcoded - chahe koi bhi login ho
 *   search box       kuch nahi karta tha
 *   bell             kuch nahi karta tha
 *   profile button   khulta hi nahi tha - yaani admin panel se
 *                    logout ka koi raasta hi nahi tha
 *
 * Ab chaaron asli hain: naam token se, bell par pending escalations
 * ki ginti, search queries page par le jata hai, aur profile mein
 * logout hai.
 */

import { Bell, ChevronDown, LogOut, PanelLeftOpen, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { adminFetch } from "@/app/admin/useAdminApi";

export default function Header({ onMenuClick }) {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [term, setTerm] = useState("");

  const menuRef = useRef(null);

  useEffect(() => {
    // Token mein naam nahi hota - sirf email (sub), user_id aur role.
    // Is liye email hi dikhaya jata hai; wo kam az kam asli hai.
    const token = localStorage.getItem("access_token");
    const sub = token ? readClaim(token, "sub") : null;
    if (sub) setEmail(sub);

    // Bell par pending escalations - jhoota badge rakhne ka koi
    // faida nahi.
    adminFetch("/livekit/admin/escalations?limit=100")
      .then((rows) =>
        setPending(
          Array.isArray(rows)
            ? rows.filter((r) => r.status === "pending").length
            : 0
        )
      )
      .catch(() => {
        /* header ki wajah se page na ruke */
      });
  }, []);

  // Bahar click karne par menu band
  useEffect(() => {
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const logout = () => {
    for (const k of [
      "access_token",
      "refresh_token",
      "token_type",
      "auth_response",
      "role",
    ]) {
      localStorage.removeItem(k);
    }
    window.dispatchEvent(new Event("auth-change"));
    window.location.href = "/login";
  };

  const submitSearch = (e) => {
    e.preventDefault();
    const q = term.trim();
    router.push(q ? `/admin/queries?q=${encodeURIComponent(q)}` : "/admin/queries");
  };

  return (
    <header className="sticky top-4 z-30 rounded-2xl border border-white/10 bg-white/[0.04] shadow-[0_8px_40px_rgba(0,0,0,0.35)] backdrop-blur-2xl">
      <div className="flex h-16 items-center justify-between gap-3 px-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-text-secondary transition-colors hover:bg-white/[0.12] hover:text-white md:hidden"
            onClick={onMenuClick}
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>

          <form
            onSubmit={submitSearch}
            className="relative hidden w-72 items-center md:flex"
          >
            <span className="pointer-events-none absolute left-3 text-text-secondary">
              <Search className="h-4 w-4" />
            </span>
            <input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Search queries…"
              className="w-full rounded-xl border border-white/10 bg-white/[0.06] py-2.5 pl-9 pr-3 text-xs text-white placeholder:text-text-secondary/70 outline-none transition-colors focus:border-accent-primary/50 focus:bg-white/[0.09] focus:ring-2 focus:ring-accent-primary/40"
            />
          </form>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push("/admin/escalations")}
            title={
              pending
                ? `${pending} escalation${pending === 1 ? "" : "s"} waiting`
                : "No pending escalations"
            }
            className="relative inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-text-secondary transition-colors hover:bg-white/[0.12] hover:text-white"
          >
            <Bell className="h-4 w-4" />
            {pending > 0 && (
              <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-amber-400 px-1 text-[10px] font-bold text-[#05041c]">
                {pending > 9 ? "9+" : pending}
              </span>
            )}
          </button>

          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-white/[0.12] hover:text-white"
            >
              <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary text-[11px] font-semibold text-[#05041c]">
                {initialsFrom(email)}
              </span>
              <span className="hidden max-w-[160px] truncate sm:inline">
                {email || "Admin"}
              </span>
              <ChevronDown className="h-3 w-3" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-2xl border border-white/10 bg-[#0b0a2a]/95 shadow-2xl backdrop-blur-xl">
                <div className="border-b border-white/10 px-4 py-3">
                  <p className="truncate text-xs text-white">
                    {email || "Admin"}
                  </p>
                  <p className="mt-0.5 text-[11px] text-text-secondary">
                    Administrator
                  </p>
                </div>
                <button
                  type="button"
                  onClick={logout}
                  className="flex w-full items-center gap-2 px-4 py-3 text-left text-xs text-text-secondary hover:bg-white/5 hover:text-white"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

/** "admin@vocira.com" -> "AV" */
function initialsFrom(email) {
  if (!email) return "AD";
  const [local, domain] = email.split("@");
  const a = (local || "")[0] || "";
  const b = (domain || "")[0] || "";
  return (a + b).toUpperCase() || "AD";
}

/** JWT se ek claim - base64url ko base64 mein badal kar. */
function readClaim(token, key) {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded))?.[key] || null;
  } catch {
    return null;
  }
}
