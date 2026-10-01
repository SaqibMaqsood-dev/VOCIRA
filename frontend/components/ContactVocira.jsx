"use client";

import { MessageCircle } from "lucide-react";

import Modal from "@/app/admin/_components/ui/Modal";
import { VOCIRA_WHATSAPP, VOCIRA_WHATSAPP_URL } from "@/lib/contact";

/**
 * "Contact us" on Vocira's own site: for a school that wants Vocira - the
 * WhatsApp number, and a button that opens the chat in WhatsApp.
 */
export default function ContactVocira({ onClose }) {
  return (
    <Modal
      id="contact-vocira"
      title="Contact Vocira"
      description="Want Vocira for your school, or have a question? Message us on WhatsApp."
      onClose={onClose}
    >
      <div className="flex flex-col items-center gap-4 py-2 text-center">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-[#25D366]/15">
          <MessageCircle className="h-7 w-7 text-[#25D366]" />
        </span>

        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-text-secondary">WhatsApp</p>
          <p id="contact-whatsapp-number" className="mt-1 font-mono text-lg font-semibold text-text-primary">
            {VOCIRA_WHATSAPP}
          </p>
        </div>

        <a
          id="contact-whatsapp-button"
          href={VOCIRA_WHATSAPP_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#25D366] px-5 py-3 text-sm font-semibold text-[#05220f] shadow-card transition hover:brightness-110"
        >
          <MessageCircle className="h-4 w-4" />
          Chat on WhatsApp
        </a>
      </div>
    </Modal>
  );
}
