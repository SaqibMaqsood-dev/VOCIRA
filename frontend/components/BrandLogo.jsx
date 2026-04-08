"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

function BrandIcon({ className }) {
  return (
    <svg
      viewBox="0 0 64 64"
      aria-hidden="true"
      className={cn("h-10 w-10", className)}
    >
      <defs>
        <linearGradient id="vociraRing" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8BE9FD" />
          <stop offset="48%" stopColor="#6C63FF" />
          <stop offset="100%" stopColor="#4f45d1" />
        </linearGradient>
        <linearGradient id="vociraCore" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8BE9FD" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#6C63FF" stopOpacity="0.95" />
        </linearGradient>
      </defs>
      <rect
        x="4"
        y="4"
        width="56"
        height="56"
        rx="16"
        fill="rgba(255,255,255,0.06)"
        stroke="rgba(255,255,255,0.16)"
      />
      <circle cx="32" cy="32" r="16" fill="none" stroke="url(#vociraRing)" strokeWidth="2.5" />
      <circle cx="32" cy="32" r="9.5" fill="url(#vociraCore)" fillOpacity="0.28" />
      <g
        fill="none"
        stroke="#F4FCFF"
        strokeWidth="2.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="28.6" y="23.5" width="6.8" height="13.2" rx="3.4" />
        <path d="M24.8 31.8v1.8c0 4 3.2 7.2 7.2 7.2s7.2-3.2 7.2-7.2v-1.8" />
        <path d="M32 40.8v4.4" />
        <path d="M28.4 45.2h7.2" />
      </g>
    </svg>
  );
}

export default function BrandLogo({ variant = "full", className }) {
  if (variant === "icon") {
    return <BrandIcon className={className} />;
  }

  if (variant === "compact") {
    return (
      <div className={cn("inline-flex items-center gap-2", className)}>
        <BrandIcon className="h-9 w-9 sm:h-10 sm:w-10" />
        <span className="text-base font-semibold tracking-[0.01em] text-text-primary sm:text-lg">
          Vocira
        </span>
      </div>
    );
  }

  return (
    <motion.div
      className={cn("inline-flex items-center gap-3", className)}
      whileHover={{ y: -1 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <BrandIcon className="h-10 w-10" />
      <span className="bg-gradient-to-r from-[#EAF8FF] via-[#C7D8FF] to-[#B8B8D1] bg-clip-text text-xl font-semibold tracking-[0.02em] text-transparent">
        Vocira
      </span>
    </motion.div>
  );
}

