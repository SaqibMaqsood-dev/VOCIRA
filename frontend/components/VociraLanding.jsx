"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  BookOpen,
  Headset,
  Languages,
  Lock,
  Mic,
  ShieldCheck,
} from "lucide-react";

import FeatureCard from "@/components/FeatureCard";
import RobotBot from "@/components/RobotBot";

/**
 * Vocira's own home page - the plain address (localhost:3000, and
 * vocira.com when deployed). It says what Vocira is and how a school
 * gets it. There is no assistant here: every school has its own
 * address, and a parent who lands here is sent to their school's link.
 */

// Vocira's own robot - the main address only; a school's site keeps its own
export const VOCIRA_ROBOT = "/lottie/vocira-robot.json";

const WHAT_IT_DOES = [
  {
    icon: BookOpen,
    title: "Answers from the school's own information",
    description:
      "Admissions, fees, timetables, events, rules - the assistant answers from the documents and pages the school gives it, not from guesses.",
  },
  {
    icon: Languages,
    title: "Speaks Urdu and English",
    description:
      "Parents talk the way they talk at home. The assistant listens and answers in the language they choose.",
  },
  {
    icon: ShieldCheck,
    title: "A child's records - only for their guardian",
    description:
      "Signed-in guardians hear their own child's attendance, results, marks and fees, read live from the school's records system. Nobody else can.",
  },
  {
    icon: Headset,
    title: "Hands over to a person",
    description:
      "When a parent asks for a person, the assistant calls the school's staff into the conversation.",
  },
];

export default function VociraLanding() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-5">
      {/* ---- what Vocira is ---- */}
      <section className="grid min-h-[calc(100vh-4rem-2.5rem-5rem)] items-center gap-10 py-8 lg:min-h-[calc(100vh-4rem-2.5rem)] lg:grid-cols-2 lg:gap-12">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1 text-xs font-medium text-text-secondary">
            <Mic className="h-3.5 w-3.5 text-accent-secondary" aria-hidden="true" />
            Voice assistant for schools
          </span>
          <h1 className="mt-4 text-balance text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl lg:text-5xl">
            Every school&apos;s own voice assistant for parents.
          </h1>
          <p className="mt-5 max-w-xl text-pretty text-base leading-7 text-text-secondary sm:text-lg">
            Vocira answers parents&apos; questions by voice, in Urdu or English, from the school&apos;s own
            information - and tells a signed-in guardian about their own child. Each school has its own
            assistant, its own address and its own data.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
              <Link href="/how-it-works" className="gradient-btn">
                <span className="relative">How it works</span>
              </Link>
            </motion.div>
            <Link
              href="/features"
              className="rounded-full border border-white/15 px-6 py-3 text-sm font-semibold text-text-secondary transition hover:border-white/30 hover:text-text-primary"
            >
              Features
            </Link>
          </div>

          <div id="parent-note" className="glass mt-8 max-w-xl px-4 py-3 text-sm text-text-secondary">
            <span className="font-semibold text-text-primary">Are you a parent? </span>
            Open the assistant link your school shares - on its website, in a notice or as a QR code. It takes you
            straight to your school&apos;s assistant.
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.06 }}
        >
          <RobotBot className="mx-auto" href="/how-it-works" label="How Vocira works" src={VOCIRA_ROBOT} />
        </motion.div>
      </section>

      {/* ---- what it does ---- */}
      <section id="what-it-does" className="scroll-mt-24 py-10">
        <h2 className="text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">What Vocira does</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          The questions a school office answers all day - answered the moment a parent asks.
        </p>
        <div className="mt-8 grid gap-5 sm:grid-cols-2">
          {WHAT_IT_DOES.map((item) => (
            <FeatureCard key={item.title} icon={item.icon} title={item.title} description={item.description} />
          ))}
        </div>
      </section>

      {/* ---- every school separate ---- */}
      <section className="py-10">
        <div className="glass flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:p-8">
          <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-accent-primary/15">
            <Lock className="size-7 text-accent-secondary" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Every school is kept apart</h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              Its own address, knowledge base, records connection and staff accounts. A school&apos;s parents and
              staff see only their school - never another school&apos;s information, or that other schools use
              Vocira.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
