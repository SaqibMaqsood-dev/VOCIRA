"use client";

import { motion } from "framer-motion";
import StatsCard from "@/components/StatsCard";
import CallTable from "@/components/CallTable";
import { demoCalls } from "@/lib/data";

export default function DashboardPage() {
  const total = demoCalls.length;
  const answered = demoCalls.filter((c) => c.status === "Answered").length;
  const missed = demoCalls.filter((c) => c.status === "Missed").length;
  const pending = demoCalls.filter((c) => c.status === "Pending").length;

  return (
    <div className="page-shell flex flex-col justify-center">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
      >
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">
          My Calls
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          Track your voice sessions, outcomes, and response handling status.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut", delay: 0.06 }}
        className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <StatsCard label="Total Calls" value={total} accent="primary" />
        <StatsCard label="Answered" value={answered} accent="secondary" />
        <StatsCard label="Missed" value={missed} accent="primary" />
        <StatsCard label="Pending" value={pending} accent="secondary" />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut", delay: 0.12 }}
        className="mt-6"
      >
        <CallTable rows={demoCalls} />
      </motion.div>
    </div>
  );
}

