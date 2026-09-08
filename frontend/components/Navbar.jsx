"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import BrandLogo from "@/components/BrandLogo";

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

  /*
   * Logout
   */
  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("role");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("auth_response");

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
          <BrandLogo className="hidden md:inline-flex" />

          <BrandLogo
            variant="compact"
            className="md:hidden"
          />
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden items-center gap-2 md:flex">
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
                {/* Kaun login hai - pehle iska koi nishaan hi
                    nahi tha, sirf "Logout" para rehta tha aur
                    ye pata nahi chalta ke kis ka session hai. */}
                {/* Chip jagah ke hisab se simat jata hai: chhoti
                    screen par sirf avatar, phir naam, aur email
                    sirf bari screen par. Warna nav bar se bahar
                    nikal jata tha aur Logout hi nazar na aata. */}
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
              </>
            )}

          </div>

          {/* Mobile menu button */}
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary hover:bg-white/10 md:hidden"
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
            className="border-b border-white/10 bg-bg-primary/95 py-3 backdrop-blur-xl md:hidden"
          >
            <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4">

              {/* Navigation */}
              {navItems.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname?.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() =>
                      setMobileOpen(false)
                    }
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm font-medium",
                      active
                        ? "bg-white/10 text-text-primary"
                        : "text-text-secondary hover:bg-white/5 hover:text-text-primary"
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}

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
 * JWT se naam aur email.
 *
 * Login ke waqt backend token mein "name" bhi daalta hai (pehle sirf
 * sub/user_id/role thay). Us se pehle UI ke paas naam tha hi nahi -
 * "Muhammad Ahmed" ki jagah "ahmed@test.com" dikhana parta.
 *
 * Signature yahan nahi jaanchi jati: ye sirf dikhane ke liye hai,
 * asli rok har API call par backend lagata hai.
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
