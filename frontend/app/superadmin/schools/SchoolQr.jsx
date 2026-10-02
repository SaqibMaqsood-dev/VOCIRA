"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Check, Copy, Download, X } from "lucide-react";

import { OverPage } from "@/app/admin/_components/ui/Modal";

/**
 * A school's own assistant address as a QR code - to print on a notice,
 * the school's website or a parents' WhatsApp group. Scanning it opens
 * the Assistant for that school, and only that school.
 */
export default function SchoolQr({ school, link, onClose }) {
  const [image, setImage] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(link, { width: 480, margin: 2, errorCorrectionLevel: "M" })
      .then((url) => !cancelled && setImage(url))
      .catch(() => !cancelled && setImage(""));
    return () => {
      cancelled = true;
    };
  }, [link]);

  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* the link is on screen to copy by hand */
    }
  }

  return (
    <OverPage>
      <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm" onClick={onClose}>
        <div
          id="school-qr"
          role="dialog"
          aria-modal="true"
          aria-label={`QR code for ${school.name}`}
          className="w-full max-w-sm rounded-2xl border border-white/10 bg-bg-secondary p-6 text-center shadow-card"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-4 text-left">
            <div>
              <h2 className="text-base font-semibold text-white">{school.name}</h2>
              <p className="mt-1 text-xs text-text-secondary">Guests scan this to call the assistant for this school.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-1 text-text-secondary hover:text-white" title="Close">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mx-auto mt-5 grid h-60 w-60 place-items-center rounded-xl bg-white p-2">
            {image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img id="school-qr-image" src={image} alt={`QR code for ${link}`} className="h-full w-full" />
            ) : (
              <span className="text-xs text-slate-500">Making the code…</span>
            )}
          </div>

          <p id="school-qr-link" className="mt-4 break-all font-mono text-[11px] text-text-secondary">
            {link}
          </p>

          <div className="mt-4 flex justify-center gap-2">
            <button
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-text-secondary hover:border-white/20 hover:text-white"
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy link"}
            </button>
            <a
              id="school-qr-download"
              href={image || undefined}
              download={`vocira-${school.id}-qr.png`}
              aria-disabled={!image}
              className={`inline-flex items-center gap-1.5 rounded-lg bg-accent-primary/80 px-3 py-2 text-xs font-medium text-white hover:bg-accent-primary ${
                image ? "" : "pointer-events-none opacity-50"
              }`}
            >
              <Download className="h-3.5 w-3.5" />
              Download PNG
            </a>
          </div>
        </div>
      </div>
    </OverPage>
  );
}
