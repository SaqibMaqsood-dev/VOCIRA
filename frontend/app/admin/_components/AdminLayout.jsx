"use client";

/**
 * Admin panel ka dhaancha.
 *
 * Pehle sidebar aur header viewport ke kinaron se chipke hue thay -
 * chapte rectangles, koi radius nahi, aur neeche chalta GradFlow
 * gradient un ke peeche gum ho jata tha.
 *
 * Ab teenon hisse floating cards hain: chaaron taraf thori jagah
 * (p-3/p-4), rounded, aur background un ke darmiyan se nazar aata
 * hai. Sidebar aur header sticky hain, sirf content scroll hota hai.
 */

import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import PageTransition from "./PageTransition";

export default function AdminLayout({ children }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen gap-3 p-3 text-white sm:gap-4 sm:p-4">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggle={() => setCollapsed(!collapsed)}
        onMobileClose={() => setMobileOpen(false)}
      />

      {/* min-w-0 zaroori hai: is ke baghair lambi tables flex item ko
          phaila deti hain aur poora page ufqi scroll karne lagta hai */}
      <div className="flex min-w-0 flex-1 flex-col gap-3 sm:gap-4">
        <Header onMenuClick={() => setMobileOpen((open) => !open)} />

        <main className="min-w-0 flex-1 pb-2">
          <div className="mx-auto w-full max-w-[1400px]">
            <PageTransition>{children}</PageTransition>
          </div>
        </main>
      </div>
    </div>
  );
}
