"use client";

import {
  AudioLines,
  BrainCircuit,
  ShieldCheck,
  Radio,
  History,
  Sparkles
} from "lucide-react";
import { motion } from "framer-motion";
import FeatureCard from "@/components/FeatureCard";

const features = [
  {
    icon: AudioLines,
    title: "Voice Based Query System",
    description:
      "Ask school-related questions naturally through real-time voice interaction."
  },
  {
    icon: BrainCircuit,
    title: "AI Powered Response Generation",
    description: "Get instant, accurate answers powered by your OpenAI + RAG stack."
  },
  {
    icon: ShieldCheck,
    title: "Sensitive Data Protection",
    description:
      "Privacy-first handling with secure processing patterns across the platform."
  },
  {
    icon: Radio,
    title: "LiveKit Voice Communication",
    description: "Low-latency audio sessions for a seamless conversational experience."
  },
  {
    icon: History,
    title: "Query History Tracking",
    description: "Review past voice queries and outcomes with clear status indicators."
  },
  {
    icon: Sparkles,
    title: "Context Aware Answers",
    description: "Responses grounded in context for better accuracy and relevance."
  }
];

export default function FeaturesPage() {
  return (
    <div className="page-shell flex flex-col justify-center">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
      >
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">
          Features
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          Built for real-time voice experiences with an AI-first, secure, and modern
          architecture.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut", delay: 0.06 }}
        className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
      >
        {features.map((f) => (
          <FeatureCard
            key={f.title}
            icon={f.icon}
            title={f.title}
            description={f.description}
          />
        ))}
      </motion.div>
    </div>
  );
}

