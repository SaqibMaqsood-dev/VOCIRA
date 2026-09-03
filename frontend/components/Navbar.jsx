"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu } from "lucide-react";
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

  /*
   * Check whether the user is authenticated.
   */
  const checkAuth = () => {
    const accessToken =
      localStorage.getItem("access_token");

    setIsLoggedIn(Boolean(accessToken));
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
        <div className="flex items-center gap-2">

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

                {/* Create Account */}
                <Link
                  href="/signup"
                  className="group relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-semibold text-text-primary shadow-card transition-transform hover:-translate-y-0.5"
                >
                  <span className="absolute -left-24 top-1/2 h-24 w-24 -translate-y-1/2 rotate-12 bg-accent-primary/35 blur-2xl transition-opacity group-hover:opacity-90" />

                  <span className="relative">
                    Create Account
                  </span>
                </Link>
              </>
            ) : (
              /* Logout */
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-xl px-4 py-2 text-sm font-semibold text-text-secondary transition-colors hover:text-text-primary"
              >
                Logout
              </button>
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

                    {/* Create Account */}
                    <Link
                      href="/signup"
                      onClick={() =>
                        setMobileOpen(false)
                      }
                      className="rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm font-semibold text-text-primary shadow-card"
                    >
                      Create Account
                    </Link>
                  </>
                ) : (
                  /* Mobile Logout */
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="rounded-lg px-3 py-2 text-left text-sm font-semibold text-text-secondary hover:bg-white/5 hover:text-text-primary"
                  >
                    Logout
                  </button>
                )}

              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}