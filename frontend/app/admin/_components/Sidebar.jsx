"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  MessageCircle,
  BookOpen,
  AlertTriangle,
  PanelLeftClose,
  PanelLeftOpen
} from "lucide-react";

const items = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/queries", label: "Queries", icon: MessageCircle },
  { href: "/admin/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/admin/escalations", label: "Escalations", icon: AlertTriangle }
];

export default function Sidebar({
  collapsed,
  mobileOpen,
  onToggle,
  onMobileClose
}) {
  const pathname = usePathname();

  return (
    <>
      <aside
        className={cn(
          "relative hidden border-r border-white/10 bg-[#05041c]/60 backdrop-blur-xl transition-all duration-300 md:block",
          collapsed ? "w-[72px]" : "w-60"
        )}
      >
        <div className="flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/5 text-xs font-semibold tracking-wide text-white">
              V
            </span>
            {!collapsed && (
              <span className="text-sm font-semibold tracking-wide text-white">
                Vocira Admin
              </span>
            )}
          </Link>
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-xs text-text-secondary hover:bg-white/10"
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </button>
        </div>

        <nav className="mt-4 space-y-1 px-2">
          {items.map((item) => {
            const active =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium text-text-secondary hover:bg-white/5 hover:text-white",
                  active && "bg-white/10 text-white"
                )}
              >
                <Icon className="h-4 w-4" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </aside>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 border-r border-white/10 bg-[#05041c]/60 backdrop-blur-xl transition-transform duration-300 md:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/5 text-xs font-semibold tracking-wide text-white">
              V
            </span>
            <span className="text-sm font-semibold tracking-wide text-white">
              Vocira Admin
            </span>
          </Link>
        </div>

        <nav className="mt-4 space-y-1 px-2">
          {items.map((item) => {
            const active =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onMobileClose}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium text-text-secondary hover:bg-white/5 hover:text-white",
                  active && "bg-white/10 text-white"
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
}

