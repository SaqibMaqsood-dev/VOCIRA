"use client";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import BackgroundGradient from "../components/BackgroundGradient";
import Providers from "./providers";
import { usePathname } from "next/navigation";


export default function AppChrome({ children }) {
  const pathname = usePathname();
  const isAdmin = pathname?.startsWith("/admin");

  // Background dono taraf. Pehle admin ye branch se seedha nikal
  // jata tha, is liye panel par gradient tha hi nahi.
  //
  // Mount ek hi jagah hai - GradFlow ek WebGL canvas hai, har page
  // par apna context banana faltu hai.
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
      <main className="relative flex-1">
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
    </>
  );
}

