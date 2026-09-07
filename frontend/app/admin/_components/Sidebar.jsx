"use client";

/**
 * Admin sidebar.
 *
 * Pehle ye viewport ke kinare se chipka hua chapta rectangle tha -
 * koi radius nahi, aur neeche chalta GradFlow gradient us ke peeche
 * dab jata tha. Ab ye ek floating glass panel hai: chaaron taraf
 * thori jagah, rounded, aur background us ke aas paas nazar aata hai.
 *
 * Nav ka rendering ek hi jagah (NavList) - pehle desktop aur mobile
 * ke liye wahi code do baar likha hua tha.
 *
 * Escalations wale item par pending ki asli ginti aati hai. Jhoota
 * badge lagane ka koi faida nahi tha, is liye pehle koi tha hi nahi -
 * magar yehi wo cheez hai jo admin ko foran nazar aani chahiye.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  LayoutDashboard,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { adminFetch } from "@/app/admin/useAdminApi";

const items = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/queries", label: "Queries", icon: MessageCircle },
  { href: "/admin/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/admin/escalations", label: "Escalations", icon: AlertTriangle },
];

export default function Sidebar({
  collapsed,
  mobileOpen,
  onToggle,
  onMobileClose,
}) {
  const pathname = usePathname();
  const [pending, setPending] = useState(0);

  useEffect(() => {
    adminFetch("/livekit/admin/escalations?limit=100")
      .then((rows) =>
        setPending(
          Array.isArray(rows)
            ? rows.filter((r) => r.status === "pending").length
            : 0
        )
      )
      .catch(() => {
        /* sidebar ki wajah se page na ruke */
      });
  }, []);

  return (
    <>
      {/* ---------- desktop ---------- */}
      <aside
        className={cn(
          "sticky top-4 hidden h-[calc(100vh-2rem)] shrink-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-2xl transition-[width] duration-300 md:flex",
          collapsed ? "w-[76px]" : "w-60"
        )}
      >
        <Brand collapsed={collapsed} onToggle={onToggle} />

        {collapsed && <ExpandButton onToggle={onToggle} />}

        <NavList
          items={items}
          pathname={pathname}
          collapsed={collapsed}
          pending={pending}
        />

        {!collapsed && (
          <div className="mt-auto border-t border-white/10 px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.16em] text-text-secondary/70">
              Vocira
            </p>
            <p className="mt-0.5 text-[11px] text-text-secondary">
              AI voice assistant
            </p>
          </div>
        )}
      </aside>

      {/* ---------- mobile ---------- */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onMobileClose}
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-3 left-3 z-50 flex w-64 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0b0a2a]/90 shadow-2xl backdrop-blur-2xl transition-transform duration-300 md:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-[110%]"
        )}
      >
        <Brand collapsed={false} onNavigate={onMobileClose} />

        <NavList
          items={items}
          pathname={pathname}
          collapsed={false}
          pending={pending}
          onNavigate={onMobileClose}
        />
      </aside>
    </>
  );
}

function Brand({ collapsed, onToggle, onNavigate }) {
  return (
    <div
      className={cn(
        "flex h-16 shrink-0 items-center gap-2 border-b border-white/10 px-4",
        collapsed && "justify-center px-0"
      )}
    >
      <Link
        href="/admin"
        onClick={onNavigate}
        className="flex min-w-0 items-center gap-2.5"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent-primary to-accent-secondary text-sm font-bold text-[#05041c] shadow-lg">
          V
        </span>
        {!collapsed && (
          <span className="truncate text-sm font-semibold tracking-wide text-white">
            Vocira Admin
          </span>
        )}
      </Link>

      {onToggle && !collapsed && (
        <button
          type="button"
          onClick={onToggle}
          title="Collapse sidebar"
          className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary transition-colors hover:bg-white/10 hover:text-white"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      )}

    </div>
  );
}

/** Collapsed halat mein toggle apni row mein - warna wo pehle nav
 *  item par chadh jata tha. */
function ExpandButton({ onToggle }) {
  return (
    <div className="flex justify-center border-b border-white/10 py-2">
      <button
        type="button"
        onClick={onToggle}
        title="Expand sidebar"
        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-text-secondary transition-colors hover:bg-white/10 hover:text-white"
      >
        <PanelLeftOpen className="h-4 w-4" />
      </button>
    </div>
  );
}

function NavList({ items, pathname, collapsed, pending, onNavigate }) {
  return (
    <nav className={cn("mt-4 space-y-1", collapsed ? "px-2" : "px-3")}>
      {items.map((item) => {
        const active =
          item.href === "/admin"
            ? pathname === "/admin"
            : pathname.startsWith(item.href);

        const Icon = item.icon;
        const badge = item.href === "/admin/escalations" ? pending : 0;

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={cn(
              "group relative flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition-all",
              collapsed ? "justify-center px-0" : "px-3",
              active
                ? "bg-gradient-to-r from-accent-primary/25 to-accent-primary/[0.06] text-white"
                : "text-text-secondary hover:bg-white/[0.06] hover:text-white"
            )}
          >
            {/* chalti hui cheez ka nishaan - bayein taraf patli patti */}
            {active && (
              <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent-secondary" />
            )}

            <Icon
              className={cn(
                "h-[18px] w-[18px] shrink-0 transition-colors",
                active
                  ? "text-accent-secondary"
                  : "text-text-secondary group-hover:text-white"
              )}
            />

            {!collapsed && <span className="truncate">{item.label}</span>}

            {badge > 0 && (
              <span
                className={cn(
                  "grid h-5 min-w-5 place-items-center rounded-full bg-amber-400 px-1.5 text-[10px] font-bold text-[#05041c]",
                  collapsed
                    ? "absolute right-1.5 top-1.5 h-4 min-w-4 px-1 text-[9px]"
                    : "ml-auto"
                )}
              >
                {badge > 9 ? "9+" : badge}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
