"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export default function StatsCard({
  label,
  value,
  accent = "primary",
  className
}) {
  const accentClass =
    accent === "secondary"
      ? "from-accent-secondary/25 to-accent-primary/10"
      : "from-accent-primary/25 to-accent-secondary/10";

  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 360, damping: 28 }}
      className={cn(
        "relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.05] p-5 shadow-card backdrop-blur-xl",
        className
      )}
    >
      <div className={cn("absolute inset-0 bg-gradient-to-br", accentClass)} />
      <div className="absolute inset-0 opacity-40 [mask-image:radial-gradient(250px_120px_at_30%_20%,black,transparent)]">
        <div className="absolute -left-20 -top-20 size-52 rounded-full bg-white/10 blur-2xl" />
      </div>

      <div className="relative">
        <p className="text-sm font-medium text-text-secondary">{label}</p>
        <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
          {value}
        </p>
      </div>
    </motion.div>
  );
}

