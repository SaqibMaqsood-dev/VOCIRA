"use client";

/**
 * The admin sidebar.
 *
 * This used to be a flat rectangle stuck to the edge of the viewport
 * - no radius, with the GradFlow gradient running underneath buried
 * behind it. It is now a floating glass panel: a little space on
 * every side, rounded, with the background visible around it.
 *
 * The nav is rendered in one place (NavList) - the same code used to
 * be written twice, once for desktop and once for mobile.
 *
 * The Escalations item carries the real pending count. A fake badge
 * would have been worthless, which is why there was none - but this
 * is exactly the thing an admin should see at a glance.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  LayoutDashboard,
  MessageCircle,
  School,
  PanelLeftClose,
  PanelLeftOpen,
  Ticket,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import BrandLogo from "@/components/BrandLogo";
import { adminFetch } from "@/app/admin/useAdminApi";

// A school's admin panel. Schools are not here: adding and removing
// schools is the platform super admin's (app/superadmin).
export const ADMIN_ITEMS = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/queries", label: "Queries", icon: MessageCircle },
  { href: "/admin/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/admin/escalations", label: "Escalations", icon: AlertTriangle },
  // what parents sent from the Support page
  { href: "/admin/tickets", label: "Tickets", icon: Ticket },
  { href: "/admin/users", label: "Accounts", icon: Users },
];

// The platform super admin's panel.
export const SUPER_ADMIN_ITEMS = [
  { href: "/superadmin/schools", label: "Schools", icon: School },
];

export default function Sidebar({
  collapsed,
  mobileOpen,
  onToggle,
  onMobileClose,
  items = ADMIN_ITEMS,
  title = "Vocira Admin",
  home = "/admin",
  showPending = true,
}) {
  const pathname = usePathname();
  // the counts on the items: pending escalations, open tickets
  const [pending, setPending] = useState({});

  useEffect(() => {
    if (!showPending) return;
    adminFetch("/livekit/admin/escalations?limit=100")
      .then((rows) =>
        setPending((p) => ({
          ...p,
          "/admin/escalations": Array.isArray(rows) ? rows.filter((r) => r.status === "pending").length : 0,
        }))
      )
      .catch(() => {
        /* sidebar ki wajah se page na ruke */
      });
    adminFetch("/livekit/admin/tickets?status=open&limit=100")
      .then((rows) => setPending((p) => ({ ...p, "/admin/tickets": Array.isArray(rows) ? rows.length : 0 })))
      .catch(() => {
        /* sidebar ki wajah se page na ruke */
      });
    // a ticket answered on its page is no longer "open"
  }, [pathname]);

  return (
    <>
      {/* ---------- desktop ---------- */}
      <aside
        className={cn(
          "sticky top-4 hidden h-[calc(100vh-2rem)] shrink-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-2xl transition-[width] duration-300 md:flex",
          collapsed ? "w-[76px]" : "w-60"
        )}
      >
        <Brand collapsed={collapsed} onToggle={onToggle} title={title} home={home} />

        {collapsed && <ExpandButton onToggle={onToggle} />}

        <NavList
          items={items}
          pathname={pathname}
          collapsed={collapsed}
          pending={pending}
          home={home}
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
        <Brand collapsed={false} onNavigate={onMobileClose} title={title} home={home} />

        <NavList
          items={items}
          pathname={pathname}
          collapsed={false}
          pending={pending}
          onNavigate={onMobileClose}
          home={home}
        />
      </aside>
    </>
  );
}

function Brand({ collapsed, onToggle, onNavigate, title = "Vocira Admin", home = "/admin" }) {
  return (
    <div
      className={cn(
        "flex h-16 shrink-0 items-center gap-2 border-b border-white/10 px-4",
        collapsed && "justify-center px-0"
      )}
    >
      <Link
        href={home}
        onClick={onNavigate}
        className="flex min-w-0 items-center gap-2.5"
      >
        <BrandLogo variant="icon" className="h-9 w-9 shrink-0" />
        {!collapsed && (
          <span className="truncate text-sm font-semibold tracking-wide text-white">
            {title}
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

/** When collapsed, the toggle gets its own row - otherwise it rode
 *  up over the first nav item. */
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

function NavList({ items, pathname, collapsed, pending, onNavigate, home = "/admin" }) {
  return (
    <nav className={cn("mt-4 space-y-1", collapsed ? "px-2" : "px-3")}>
      {items.map((item) => {
        const active =
          item.href === home
            ? pathname === home
            : pathname.startsWith(item.href);

        const Icon = item.icon;
        const badge = pending[item.href] || 0;

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
            {/* marks the active item - a thin bar on the left */}
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
