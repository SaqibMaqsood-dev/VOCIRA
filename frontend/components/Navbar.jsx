"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { authFetch, clearSession } from "@/lib/session";
import BrandLogo from "@/components/BrandLogo";
import LanguageSelect, {
  readGuestLanguage,
  writeGuestLanguage,
} from "@/components/LanguageSelect";

// What a call runs in - one choice covers all of it: what the
// assistant listens for, what it answers in, and which voice speaks.
//
// Urdu is what an account that has never chosen already runs as, so
// it is shown as the selected one rather than offering a separate
// "Default" entry that would mean the same thing twice.
const DEFAULT_LANGUAGE = "ur";

const LANGUAGES = [
  { value: "ur", label: "اردو" },
  { value: "en", label: "English" },
];


const navItems = [
  { href: "/", label: "Home" },
  { href: "/assistant", label: "Assistant" },
  { href: "/dashboard", label: "My Calls" },
  { href: "/features", label: "Features" },
  { href: "/support", label: "Support" },
];

export default function Navbar() {
  const pathname = usePathname();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [who, setWho] = useState(null);

  // null while it is still being read - showing Urdu before the
  // answer arrives would flicker past an English choice.
  const [language, setLanguage] = useState(null);
  const [savingLanguage, setSavingLanguage] = useState(false);

  // The assistant page says when a call is up. The language is
  // settled once, as the call starts, so changing it mid-call would
  // do nothing until the next one - the picker closes instead of
  // quietly lying about what the caller is hearing.
  const [callActive, setCallActive] = useState(false);

  /*
   * Check whether the user is authenticated.
   */
  const checkAuth = () => {
    const accessToken =
      localStorage.getItem("access_token");

    setIsLoggedIn(Boolean(accessToken));
    setWho(accessToken ? readUser(accessToken) : null);
  };

  /*
   * Check authentication when Navbar loads.
   *
   * Also listen for auth changes from Login/Logout.
   */
  useEffect(() => {
    checkAuth();

    const handleAuthChange = () => {
      checkAuth();
    };

    window.addEventListener(
      "auth-change",
      handleAuthChange
    );

    return () => {
      window.removeEventListener(
        "auth-change",
        handleAuthChange
      );
    };
  }, []);

  useEffect(() => {
    const handleCallState = (event) => {
      setCallActive(Boolean(event.detail?.active));
    };

    window.addEventListener("vocira-call-state", handleCallState);

    return () => {
      window.removeEventListener("vocira-call-state", handleCallState);
    };
  }, []);

  /*
   * The caller's own call language. Best-effort: not being able to
   * read it just leaves the selector on Urdu, which is what an
   * account without a choice runs as anyway.
   */
  useEffect(() => {
    // A guest can talk to Vocira too, and their choice is kept in
    // the browser - there is no account to save it to.
    if (!isLoggedIn) {
      setLanguage(readGuestLanguage(DEFAULT_LANGUAGE));
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const response = await authFetch("/auth/users/me/language");
        if (!response.ok) return;

        const data = await response.json();
        // An account that never chose has null stored, and runs as
        // the default - so that is what the selector shows.
        if (!cancelled) setLanguage(data?.language || DEFAULT_LANGUAGE);
      } catch {
        // offline or logged out mid-flight - leave it unset
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isLoggedIn]);

  const changeLanguage = async (value) => {
    if (!isLoggedIn) {
      setLanguage(value);
      writeGuestLanguage(value);
      return;
    }

    const previous = language;
    setLanguage(value);
    setSavingLanguage(true);

    try {
      const response = await authFetch("/auth/users/me/language", {
        method: "PATCH",
        body: JSON.stringify({ language: value }),
      });

      if (!response.ok) throw new Error("save failed");
    } catch {
      // Put the selector back to what is actually saved, rather than
      // leaving it showing a choice the server never accepted.
      setLanguage(previous);
    } finally {
      setSavingLanguage(false);
    }
  };

  /*
   * Logout
   */
  const handleLogout = () => {
    clearSession();

    setIsLoggedIn(false);

    /*
     * Notify other components.
     */
    window.dispatchEvent(
      new Event("auth-change")
    );

    /*
     * Close mobile menu.
     */
    setMobileOpen(false);

    /*
     * Go to login page.
     */
    window.location.href = "/login";
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-bg-primary/40 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-5">

        {/* Logo */}
        <Link
          href="/"
          className="inline-flex items-center rounded-xl py-1"
        >
          <BrandLogo className="hidden lg:inline-flex" />

          <BrandLogo
            variant="compact"
            className="lg:hidden"
          />
        </Link>

        {/* Desktop Navigation */}
        {/* Matches MobileTabBar's lg:hidden. At md these links
            appeared while the bottom bar was still there, so an
            iPad showed the same five destinations twice. */}
        <nav className="hidden items-center gap-2 lg:flex">
          {navItems.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative rounded-xl px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary",
                  active && "text-text-primary"
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 -z-10 rounded-xl border border-white/10 bg-white/[0.06] shadow-card"
                    transition={{
                      type: "spring",
                      stiffness: 380,
                      damping: 30,
                    }}
                  />
                )}

                <span className="relative">
                  {item.label}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex min-w-0 items-center gap-2">

          {/* Desktop Auth */}
          <div className="hidden items-center gap-2 sm:flex">

            {!isLoggedIn ? (
              <>
                {/* Login */}
                <Link
                  href="/login"
                  className="rounded-xl px-4 py-2 text-sm font-semibold text-text-secondary transition-colors hover:text-text-primary"
                >
                  Login
                </Link>

              </>
            ) : (
              <>
                {/* Who is logged in - there was no sign of this
                    before, just "Logout" sitting there with no way
                    to tell whose session it was. */}
                {/* The chip shrinks with the space available: on a
                    small screen the avatar only, then the name, and
                    the email only on a large screen. Otherwise it
                    pushed out of the nav bar and Logout disappeared
                    with it. */}
                <div className="flex min-w-0 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] p-1.5 shadow-card backdrop-blur-xl lg:gap-2.5 lg:pr-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-accent-primary to-accent-secondary text-xs font-bold text-[#05041c]">
                    {initialsOf(who)}
                  </span>
                  <span className="hidden min-w-0 flex-col leading-tight lg:flex">
                    <span className="max-w-[130px] truncate text-sm font-semibold text-text-primary">
                      {who?.name || who?.email || "Signed in"}
                    </span>
                    {who?.name && who?.email && (
                      <span className="max-w-[130px] truncate text-[11px] text-text-secondary">
                        {who.email}
                      </span>
                    )}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleLogout}
                  title="Log out"
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-2 text-sm font-semibold text-text-secondary transition-colors hover:border-red-400/40 hover:bg-red-400/10 hover:text-red-200 lg:px-3.5"
                >
                  <LogOut className="h-4 w-4" />
                  <span className="hidden lg:inline">Logout</span>
                </button>

                {/* The caller picks the language their own calls run
                    in - it used to be one setting for the whole
                    deployment, so every guardian got the same one. */}
                <LanguageSelect
                  value={language ?? DEFAULT_LANGUAGE}
                  options={LANGUAGES}
                  disabled={language === null || savingLanguage || callActive}
                  lockedReason="Language cannot change during a call"
                  onChange={changeLanguage}
                />
              </>
            )}

          </div>

          {/* Outside the signed-in branch on purpose: a guest can
              talk to Vocira as well, so they need to pick the
              language their call runs in too. */}
          {!isLoggedIn && (
            <div className="hidden sm:block">
              <LanguageSelect
                value={language ?? DEFAULT_LANGUAGE}
                options={LANGUAGES}
                disabled={language === null || callActive}
                lockedReason="Language cannot change during a call"
                onChange={changeLanguage}
              />
            </div>
          )}

          {/* Mobile menu button */}
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:bg-white/10 sm:hidden"
            onClick={() =>
              setMobileOpen((open) => !open)
            }
          >
            <Menu className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{
              opacity: 0,
              y: -8,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            exit={{
              opacity: 0,
              y: -8,
            }}
            transition={{
              duration: 0.18,
              ease: "easeOut",
            }}
            className="border-b border-white/10 bg-bg-primary/95 py-3 backdrop-blur-xl sm:hidden"
          >
            <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4">

              {/* The page links are in the bottom tab bar on
                  these sizes - repeating them here just gave two
                  ways to do the same thing. What is left is what
                  does not fit in five slots. */}

              {/* Mobile Auth */}
              <div className="mt-2 flex flex-col gap-2">

                {!isLoggedIn ? (
                  <>
                    {/* Login */}
                    <Link
                      href="/login"
                      onClick={() =>
                        setMobileOpen(false)
                      }
                      className="rounded-lg px-3 py-2 text-sm font-semibold text-text-secondary hover:bg-white/5 hover:text-text-primary"
                    >
                      Login
                    </Link>

                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-text-secondary">
                        Call language
                      </span>
                      <div className="ml-auto">
                        <LanguageSelect
                          value={language ?? DEFAULT_LANGUAGE}
                          options={LANGUAGES}
                          disabled={language === null || callActive}
                          lockedReason="Language cannot change during a call"
                          onChange={changeLanguage}
                        />
                      </div>
                    </div>

                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.06] px-2.5 py-2">
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-accent-primary to-accent-secondary text-xs font-bold text-[#05041c]">
                        {initialsOf(who)}
                      </span>
                      <span className="flex min-w-0 flex-col leading-tight">
                        <span className="truncate text-sm font-semibold text-text-primary">
                          {who?.name || who?.email || "Signed in"}
                        </span>
                        {who?.name && who?.email && (
                          <span className="truncate text-[11px] text-text-secondary">
                            {who.email}
                          </span>
                        )}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-text-secondary">
                        Call language
                      </span>
                      <div className="ml-auto">
                        <LanguageSelect
                          value={language ?? DEFAULT_LANGUAGE}
                          options={LANGUAGES}
                          disabled={language === null || savingLanguage || callActive}
                          lockedReason="Language cannot change during a call"
                          onChange={changeLanguage}
                        />
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={handleLogout}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-left text-sm font-semibold text-text-secondary hover:border-red-400/40 hover:bg-red-400/10 hover:text-red-200"
                    >
                      <LogOut className="h-4 w-4" />
                      Logout
                    </button>
                  </>
                )}

              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}


/**
 * Name and email from the JWT.
 *
 * At login the backend now puts "name" into the token as well (it
 * held only sub/user_id/role before). Until then the UI had no name
 * at all - it had to show "ahmed@test.com" in place of "Muhammad
 * Ahmed".
 *
 * The signature is not verified here: this is for display only, and
 * the real gate is applied by the backend on every API call.
 */
function readUser(token) {
  try {
    const part = token.split(".")[1];
    if (!part) return null;

    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const claims = JSON.parse(atob(padded));

    return { name: claims?.name || null, email: claims?.sub || null };
  } catch {
    return null;
  }
}

/** "Muhammad Ahmed" -> "MA" · "ahmed@test.com" -> "AT" */
function initialsOf(who) {
  if (who?.name) {
    const parts = who.name.trim().split(/\s+/);
    const first = parts[0]?.[0] || "";
    const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return (first + last).toUpperCase() || "U";
  }

  if (who?.email) {
    const [local, domain] = who.email.split("@");
    return ((local?.[0] || "") + (domain?.[0] || "")).toUpperCase() || "U";
  }

  return "U";
}
