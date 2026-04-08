"use client";

import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";

export default function AdminLayout({ children }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#05041c] text-white">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggle={() => setCollapsed(!collapsed)}
        onMobileClose={() => setMobileOpen(false)}
      />
      <div className="flex min-h-screen flex-1 flex-col">
        <Header onMenuClick={() => setMobileOpen((open) => !open)} />
        <main className="flex-1 bg-gradient-to-br from-[#05041c] via-[#060521] to-[#05041c] pb-6">
          <div className="mx-auto w-full max-w-6xl px-3 pt-4 sm:px-4 sm:pt-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

