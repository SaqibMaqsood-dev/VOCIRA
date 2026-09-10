"use client";

import { motion } from "framer-motion";
import AuthForm from "@/components/AuthForm";

export default function SignupPage() {
  return (
    <div className="page-shell flex items-center">
      <div className="grid h-full items-center gap-8 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="relative"
        >
          <div className="pointer-events-none absolute -left-16 -top-10 size-56 rounded-full bg-accent-primary/18 blur-3xl" />
          <h1 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Hello, Welcome.
          </h1>
          <p className="mt-3 text-lg text-text-secondary">
            Sign up to your account.
          </p>
          <div className="mt-8 glass p-6">
            <p className="text-sm leading-7 text-text-secondary">
              Create your Vocira account to start asking school questions through
              real-time voice conversation.
            </p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut", delay: 0.06 }}
          className="mx-auto w-full max-w-md"
        >
          <AuthForm
            variant="signup"
            title="Create your account"
            subtitle="Use your details to register and start calling."
            fields={[
              {
                name: "username",
                label: "Username",
                type: "text",
                placeholder: "Your username"
              },
              {
                name: "email",
                label: "Email",
                type: "email",
                placeholder: "you@example.com"
              },
              {
                name: "password",
                label: "Password",
                type: "password",
                placeholder: "Create a password"
              }
            ]}
            submitLabel="Register"
            footerText="Already have an account?"
            footerLinkLabel="Login"
            footerLinkHref="/login"
          />
        </motion.div>
      </div>
    </div>
  );
}

