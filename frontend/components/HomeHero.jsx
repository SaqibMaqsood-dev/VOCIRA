"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { School } from "lucide-react";
import RobotBot from "@/components/RobotBot";

/**
 * The home page of the assistant - on a school's own address, with
 * that school's name; for a signed-in user on the plain address,
 * without one (their calls go to their account's school).
 */
export default function HomeHero({ schoolName = "", robotSrc = null }) {
  return (
    <div className="page-shell flex items-center">
      <div className="grid w-full items-center gap-10 lg:grid-cols-2 lg:gap-12">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          {schoolName && (
            <span
              id="home-school"
              className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-accent-primary/30 bg-accent-primary/10 px-3 py-1 text-xs font-medium text-white"
            >
              <School className="h-3.5 w-3.5" aria-hidden="true" />
              {schoolName}
            </span>
          )}
          <h1 className="text-balance text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl lg:text-5xl">
            Get instant answers through real-time voice conversation.
          </h1>
          <p className="mt-5 max-w-xl text-pretty text-base leading-7 text-text-secondary sm:text-lg">
            {schoolName
              ? `Ask anything about ${schoolName} - fees, timetables, admissions, events. Parents who sign in also hear their own child's attendance, results and fees.`
              : "Vocira AI assistant helps students and parents get school information instantly."}
          </p>

          <div className="mt-8 space-y-3">
            <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
              <Link href="/assistant" className="gradient-btn">
                <span className="relative">Go to Assistant</span>
              </Link>
            </motion.div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.06 }}
          className="relative"
        >
          <RobotBot className="mx-auto" src={robotSrc} />
        </motion.div>
      </div>
    </div>
  );
}
