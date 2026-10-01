"use client";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import MobileTabBar from "../components/MobileTabBar";
import BackgroundGradient from "../components/BackgroundGradient";
import Providers from "./providers";
import { usePathname } from "next/navigation";


export default function AppChrome({ children }) {
  const pathname = usePathname();
  // Both panels bring their own frame (sidebar + header); the site's
  // navbar on top of it covered the sidebar's top when scrolling.
  const isAdmin = pathname?.startsWith("/admin") || pathname?.startsWith("/superadmin");

  // The background on both sides. Admin used to return early from
  // this branch, so the panel had no gradient at all.
  //
  // It is mounted in one place - GradFlow is a WebGL canvas, and
  // giving every page its own context is wasteful.
  if (isAdmin) {
    return (
      <>
        <BackgroundGradient />
        <Providers>{children}</Providers>
      </>
    );
  }

  return (
    <>
      <BackgroundGradient />
      <Navbar />
      {/* pb on small screens only: the tab bar is fixed, so
          without it the last thing on a page (End Call, a submit
          button) sits underneath and cannot be tapped. */}
      <main className="relative flex-1 pb-24 lg:pb-0">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[-120px] top-[140px] size-[260px] animate-floaty rounded-full bg-accent-primary/16 blur-3xl" />
          <div className="absolute right-[-140px] top-[260px] size-[320px] animate-floaty rounded-full bg-accent-secondary/10 blur-3xl [animation-delay:800ms]" />
          <div className="absolute left-[30%] bottom-[-220px] size-[420px] animate-floaty rounded-full bg-accent-primary/10 blur-3xl [animation-delay:1200ms]" />
        </div>
        <div className="relative">
          <Providers>{children}</Providers>
        </div>
      </main>
      <Footer />
      <MobileTabBar />
    </>
  );
}

