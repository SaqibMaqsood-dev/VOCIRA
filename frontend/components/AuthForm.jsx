"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export default function AuthForm({
  variant,
  title,
  subtitle,
  fields,
  submitLabel,
  footerText,
  footerLinkLabel,
  footerLinkHref,
  extra
}) {
  return (
    <div className="glass relative overflow-hidden p-7 sm:p-8">
      <div className="pointer-events-none absolute -left-24 -top-24 size-72 rounded-full bg-accent-primary/22 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-32 size-80 rounded-full bg-accent-secondary/12 blur-3xl" />

      <div className="relative">
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">
          {title}
        </h2>
        <p className="mt-2 text-sm leading-6 text-text-secondary">{subtitle}</p>

        <form className="mt-6 space-y-4">
          {fields.map((f) => (
            <label key={f.name} className="block">
              <span className="mb-2 block text-xs font-semibold tracking-wide text-text-secondary">
                {f.label}
              </span>
              <input
                name={f.name}
                type={f.type}
                placeholder={f.placeholder}
                className={cn(
                  "w-full rounded-xl border border-white/10 bg-bg-primary/30 px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60",
                  "shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur-xl",
                  "focus:outline-none focus:ring-2 focus:ring-accent-primary/60"
                )}
              />
            </label>
          ))}

          {variant === "login" && (
            <div className="flex items-center justify-end">
              <Link
                href="#"
                className="text-xs font-semibold text-text-secondary hover:text-text-primary"
              >
                Forgot Password?
              </Link>
            </div>
          )}

          {extra}

          <motion.button
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.98 }}
            className="group relative w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card"
            type="button"
          >
            <span className="absolute -left-28 top-1/2 h-28 w-28 -translate-y-1/2 rotate-12 bg-accent-primary/40 blur-2xl transition-opacity group-hover:opacity-90" />
            <span className="absolute -right-28 top-1/2 h-28 w-28 -translate-y-1/2 -rotate-12 bg-accent-secondary/22 blur-2xl transition-opacity group-hover:opacity-90" />
            <span className="relative">{submitLabel}</span>
          </motion.button>
        </form>

        <p className="mt-6 text-sm text-text-secondary">
          {footerText}{" "}
          <Link
            href={footerLinkHref}
            className="font-semibold text-text-primary hover:underline"
          >
            {footerLinkLabel}
          </Link>
        </p>
      </div>
    </div>
  );
}

