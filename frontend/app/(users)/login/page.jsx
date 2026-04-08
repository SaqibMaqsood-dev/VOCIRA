"use client";

import { motion } from "framer-motion";
import AuthForm from "@/components/AuthForm";

export default function LoginPage() {
  return (
    <div className="page-shell flex items-center">
      <div className="grid h-full items-center gap-8 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="relative"
        >
          <div className="pointer-events-none absolute -left-16 -top-10 size-56 rounded-full bg-accent-secondary/14 blur-3xl" />
          <h1 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Welcome Back.
          </h1>
          <p className="mt-3 text-lg text-text-secondary">
            Sign into your account.
          </p>
          <div className="mt-8 glass p-6">
            <p className="text-sm leading-7 text-text-secondary">
              Continue your voice sessions and access your call history.
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
            variant="login"
            title="Sign in"
            subtitle="Enter your credentials to access Vocira."
            fields={[
              {
                name: "username",
                label: "Username",
                type: "text",
                placeholder: "Your username"
              },
              {
                name: "password",
                label: "Password",
                type: "password",
                placeholder: "Your password"
              }
            ]}
            submitLabel="Login"
            footerText="Don't have an account?"
            footerLinkLabel="Create Account"
            footerLinkHref="/signup"
          />
        </motion.div>
      </div>
    </div>
  );
}

