"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, LifeBuoy, ListOrdered, Mic, PhoneCall, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSite } from "@/lib/site";

/**
 * The bottom bar phones and tablets navigate with.
 *
 * Everything used to sit behind the hamburger: two taps to reach any
 * page, and nothing on screen to say where you were. This is the
 * shape people already know from an app - the main action raised in
 * the middle, the rest either side of it.
 *
 * The hamburger stays for what does not belong in five slots: the
 * language picker and signing in or out.
 */
const LEFT = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Calls", icon: PhoneCall },
];

const RIGHT = [
  { href: "/features", label: "Features", icon: Sparkles },
  { href: "/support", label: "Support", icon: LifeBuoy },
];

// Vocira's own site: what Vocira is - no assistant there
const VOCIRA_TABS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/features", label: "Features", icon: Sparkles },
  { href: "/how-it-works", label: "How it works", icon: ListOrdered },
];

// the super admin, signed in there: back to their panel
const PANEL_TAB = { href: "/superadmin/schools", label: "Panel", icon: LayoutDashboard };

function isActive(pathname, href) {
  if (href.includes("#")) return false;
  return href === "/" ? pathname === "/" : pathname?.startsWith(href);
}

function Tab({ item, pathname }) {
  const active = isActive(pathname, item.href);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex flex-1 flex-col items-center gap-1 py-2 text-[10px] font-medium transition-colors",
        active
          ? "text-text-primary"
          : "text-text-secondary hover:text-text-primary"
      )}
    >
      <Icon className={cn("h-5 w-5", active && "text-accent-primary")} />
      {item.label}
    </Link>
  );
}

export default function MobileTabBar() {
  const pathname = usePathname();
  const assistantActive = pathname?.startsWith("/assistant");
  const site = useSite();

  if (site?.product) {
    return (
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-bg-primary/80 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
      >
        <div className="mx-auto flex max-w-md items-end justify-around px-2">
          {(site.loggedIn ? [...VOCIRA_TABS, PANEL_TAB] : VOCIRA_TABS).map((item) => (
            <Tab key={item.href} item={item} pathname={pathname} />
          ))}
        </div>
      </nav>
    );
  }

  return (
    <nav
      aria-label="Main"
      // pb keeps the bar clear of the iPhone home indicator.
      className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-bg-primary/80 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
    >
      <div className="mx-auto flex max-w-md items-end justify-around px-2">
        {LEFT.map((item) => (
          <Tab key={item.href} item={item} pathname={pathname} />
        ))}

        {/* The assistant is what people open the app for, so it gets
            the middle and sits above the bar rather than in it. */}
        <Link
          href="/assistant"
          aria-label="Assistant"
          aria-current={assistantActive ? "page" : undefined}
          className="-mt-6 flex flex-1 flex-col items-center gap-1"
        >
          <span
            className={cn(
              "grid h-14 w-14 place-items-center rounded-full shadow-lg ring-4 ring-bg-primary transition-transform active:scale-95",
              assistantActive
                ? "bg-gradient-to-br from-accent-primary to-accent-secondary"
                : "bg-gradient-to-br from-accent-primary/80 to-accent-secondary/80"
            )}
          >
            <Mic className="h-6 w-6 text-[#05041c]" />
          </span>
          <span
            className={cn(
              "pb-2 text-[10px] font-semibold",
              assistantActive ? "text-text-primary" : "text-text-secondary"
            )}
          >
            Assistant
          </span>
        </Link>

        {RIGHT.map((item) => (
          <Tab key={item.href} item={item} pathname={pathname} />
        ))}
      </div>
    </nav>
  );
}
