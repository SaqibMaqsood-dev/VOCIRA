"use client";

/**
 * The admin panel's frame.
 *
 * The sidebar and header used to be stuck to the edges of the
 * viewport - flat rectangles, no radius, and the GradFlow gradient
 * running underneath was lost behind them.
 *
 * All three parts are now floating cards: a little space on every
 * side (p-3/p-4), rounded, with the background visible between them.
 * The sidebar and header are sticky; only the content scrolls.
 */

import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import PageTransition from "./PageTransition";
import IncomingCall from "./IncomingCall";

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

      {/* min-w-0 is required: without it, wide tables stretch the
          flex item and the whole page scrolls horizontally */}
      <div className="flex min-w-0 flex-1 flex-col gap-3 sm:gap-4">
        <Header onMenuClick={() => setMobileOpen((open) => !open)} />

        <main className="min-w-0 flex-1 pb-2">
          <div className="mx-auto w-full max-w-[1400px]">
            <PageTransition>{children}</PageTransition>
          </div>
        </main>
      </div>

      {/* This lives in the layout, not in a page - a call can
          arrive at any moment, and the admin may be on Knowledge or
          Users at the time. It survives navigation, so a call in
          progress is not cut off by changing route. */}
      <IncomingCall />
    </div>
  );
}
