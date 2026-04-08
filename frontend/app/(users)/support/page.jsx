"use client";

import { motion } from "framer-motion";

export default function SupportPage() {
  return (
    <div className="page-shell flex items-center justify-center">
      <div className="relative w-full max-w-xl">
        <div className="pointer-events-none absolute -left-20 top-10 size-56 animate-floaty rounded-full bg-accent-primary/14 blur-3xl" />
        <div className="pointer-events-none absolute -right-20 top-36 size-64 animate-floaty rounded-full bg-accent-secondary/10 blur-3xl [animation-delay:900ms]" />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="glass relative p-7 sm:p-8"
        >
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">
            Support
          </h1>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            Tell us what you need help with.
          </p>

          <form className="mt-6 space-y-4">
            <label className="block">
              <span className="mb-2 block text-xs font-semibold tracking-wide text-text-secondary">
                Subject
              </span>
              <input
                type="text"
                placeholder="e.g. Can’t start voice call"
                className="w-full rounded-xl border border-white/10 bg-bg-primary/30 px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-accent-primary/60"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-semibold tracking-wide text-text-secondary">
                Message
              </span>
              <textarea
                rows={6}
                placeholder="Describe your issue..."
                className="w-full resize-none rounded-xl border border-white/10 bg-bg-primary/30 px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-accent-primary/60"
              />
            </label>

            <motion.button
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              className="group relative w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card"
            >
              <span className="absolute -left-28 top-1/2 h-28 w-28 -translate-y-1/2 rotate-12 bg-accent-primary/40 blur-2xl transition-opacity group-hover:opacity-90" />
              <span className="absolute -right-28 top-1/2 h-28 w-28 -translate-y-1/2 -rotate-12 bg-accent-secondary/18 blur-2xl transition-opacity group-hover:opacity-90" />
              <span className="relative">Submit</span>
            </motion.button>
          </form>
        </motion.div>
      </div>
    </div>
  );
}

