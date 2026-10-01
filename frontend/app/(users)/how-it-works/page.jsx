"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AudioLines,
  Building2,
  Headset,
  Link2,
  Lock,
  MessageCircle,
  Mic,
  QrCode,
  Search,
} from "lucide-react";

import ContactVocira from "@/components/ContactVocira";

/**
 * How Vocira works - for a school thinking of getting it: how a school
 * comes onto Vocira, and what happens when a parent calls.
 */

const JOINING = [
  {
    icon: Building2,
    title: "The school joins Vocira",
    description:
      "It gets its own address - like yourschool.vocira.com - with its own name, helpline and staff accounts.",
  },
  {
    icon: Link2,
    title: "Its knowledge and records are connected",
    description:
      "The school's documents go into its own knowledge base. Its records system (ERPNext, Open School MIS or a live Google Sheet) is connected with encrypted keys, and the school chooses what is shared.",
  },
  {
    icon: QrCode,
    title: "Parents open the link and talk",
    description:
      "The school shares its link on its website, in notices or as a QR code. Parents tap the microphone and ask.",
  },
];

const ON_A_CALL = [
  {
    icon: Mic,
    title: "A parent taps the microphone",
    description: "On the school's link, in Urdu or English. Nothing to install - it works in the browser.",
  },
  {
    icon: AudioLines,
    title: "The assistant listens",
    description: "It turns the parent's voice into words and works out what they are asking.",
  },
  {
    icon: Search,
    title: "It finds the answer",
    description:
      "School questions from the school's own knowledge base. A signed-in guardian's questions about their child - attendance, results, fees - live from the school's records.",
  },
  {
    icon: Headset,
    title: "It answers - or brings in a person",
    description:
      "The answer is spoken back in the parent's language. When the parent asks for a person, the school's staff are called into the conversation.",
  },
];

function Steps({ steps, columns }) {
  return (
    <ol className={`mt-8 grid gap-5 ${columns}`}>
      {steps.map((step, index) => (
        <li key={step.title} className="glass relative p-6">
          <span className="absolute right-5 top-5 text-3xl font-semibold text-white/10">{index + 1}</span>
          <div className="grid size-12 place-items-center rounded-xl border border-white/10 bg-white/[0.06] shadow-card">
            <step.icon className="size-6 text-accent-secondary" aria-hidden="true" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-text-primary">{step.title}</h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">{step.description}</p>
        </li>
      ))}
    </ol>
  );
}

export default function HowItWorksPage() {
  const [contactOpen, setContactOpen] = useState(false);

  return (
    <div className="page-shell">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
      >
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">How it works</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          From a school joining Vocira to a parent hearing their answer.
        </p>
      </motion.div>

      <motion.section
        id="school-joins"
        className="mt-10"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut", delay: 0.06 }}
      >
        <h2 className="text-xl font-semibold tracking-tight text-text-primary sm:text-2xl">A school comes onto Vocira</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
          Three steps from a school joining to parents talking to it.
        </p>
        <Steps steps={JOINING} columns="lg:grid-cols-3" />
      </motion.section>

      <motion.section
        id="on-a-call"
        className="mt-14"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut", delay: 0.12 }}
      >
        <h2 className="text-xl font-semibold tracking-tight text-text-primary sm:text-2xl">What happens on a call</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
          A parent asks out loud, and hears the answer a moment later.
        </p>
        <Steps steps={ON_A_CALL} columns="sm:grid-cols-2 lg:grid-cols-4" />
      </motion.section>

      <section className="mt-14">
        <div className="glass flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:p-8">
          <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-accent-primary/15">
            <Lock className="size-7 text-accent-secondary" aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-text-primary">Want Vocira for your school?</h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              Every school is kept apart - its own address, knowledge base, records connection and staff accounts.
              Message us and we will set yours up.
            </p>
          </div>
          <button
            id="how-it-works-contact"
            type="button"
            onClick={() => setContactOpen(true)}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-[#25D366]/40 bg-[#25D366]/10 px-5 py-3 text-sm font-semibold text-text-primary transition hover:bg-[#25D366]/20"
          >
            <MessageCircle className="h-4 w-4 text-[#25D366]" />
            Contact us
          </button>
        </div>
      </section>

      {contactOpen && <ContactVocira onClose={() => setContactOpen(false)} />}
    </div>
  );
}
