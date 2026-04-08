"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export default function FeatureCard({
  icon: Icon,
  title,
  description,
  className
}) {
  return (
    <motion.div
      whileHover={{ y: -6, scale: 1.01 }}
      transition={{ type: "spring", stiffness: 380, damping: 28 }}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.05] p-6 shadow-card backdrop-blur-xl",
        className
      )}
    >
      <div className="pointer-events-none absolute -left-24 -top-24 size-56 rounded-full bg-accent-primary/25 blur-3xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
      <div className="pointer-events-none absolute -bottom-28 -right-28 size-60 rounded-full bg-accent-secondary/16 blur-3xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" />

      <div className="flex items-start gap-4">
        <div className="grid size-12 place-items-center rounded-xl border border-white/10 bg-white/[0.06] shadow-card">
          <Icon className="size-6 text-accent-secondary" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-text-primary">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {description}
          </p>
        </div>
      </div>

      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
        <div className="absolute inset-0 rounded-xl ring-1 ring-white/10 shadow-glow" />
      </div>
    </motion.div>
  );
}

