"use client";

/**
 * Support page.
 *
 * Pehle ye ek murda form tha - type="button", koi onClick nahi, koi
 * fetch nahi. Likhein, Submit dabayein, kuch nahi hota tha.
 *
 * Ab ticket ERPNext ke Issue doctype mein banta hai. School ka banda
 * usay apne Support module mein dekhta hai (localhost:8081/app/issue)
 * - hamein koi admin screen banane ki zaroorat nahi.
 */

import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Loader2, Ticket } from "lucide-react";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function SupportPage() {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const [sending, setSending] = useState(false);
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState(null);

  const [tickets, setTickets] = useState([]);
  const [loadingList, setLoadingList] = useState(true);

  const token =
    typeof window === "undefined"
      ? null
      : localStorage.getItem("access_token");

  // ---- pehle ke tickets ----
  const loadTickets = async () => {
    if (!token || !API_URL) {
      setLoadingList(false);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/livekit/support/tickets`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const rows = await res.json();
        setTickets(Array.isArray(rows) ? rows : []);
      }
    } catch {
      // list na aaye to form phir bhi chalna chahiye
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    loadTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e) => {
    e.preventDefault();

    setError(null);
    setTicket(null);

    if (!API_URL) {
      setError("API URL set nahi hai (NEXT_PUBLIC_API_URL).");
      return;
    }

    if (!token) {
      setError("Ticket bhejne ke liye login karna zaroori hai.");
      return;
    }

    if (subject.trim().length < 3) {
      setError("Subject kam az kam 3 harf ka hona chahiye.");
      return;
    }

    setSending(true);

    try {
      const res = await fetch(`${API_URL}/livekit/support/tickets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ subject, message }),
      });

      if (res.status === 401) {
        setError("Aap ka session khatam ho gaya - dobara login karein.");
        return;
      }

      if (!res.ok) {
        // Backend ki asli wajah dikhayein, apni banai hui nahi
        let detail = `Ticket nahi ban saka (HTTP ${res.status}).`;
        try {
          const body = await res.json();
          if (body?.detail) {
            detail =
              typeof body.detail === "string"
                ? body.detail
                : JSON.stringify(body.detail);
          }
        } catch {
          /* body JSON nahi thi */
        }
        setError(detail);
        return;
      }

      const data = await res.json();
      setTicket(data);
      setSubject("");
      setMessage("");
      loadTickets();
    } catch {
      setError(
        "Server se rabta nahi ho saka. Dekh lein ke API Gateway chal raha hai."
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page-shell flex items-start justify-center py-10">
      <div className="relative w-full max-w-xl">
        <div className="pointer-events-none absolute -left-20 top-10 size-56 animate-floaty rounded-full bg-accent-primary/14 blur-3xl" />
        <div className="pointer-events-none absolute -right-20 top-36 size-64 animate-floaty rounded-full bg-accent-secondary/10 blur-3xl [animation-delay:900ms]" />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="glass relative p-7 sm:p-8"
        >
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">
            Support
          </h1>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            Tell us what you need help with.
          </p>

          {/* ---- ticket ban gaya ---- */}
          {ticket && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-5 rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-4"
            >
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
                <div>
                  <p className="text-sm font-semibold text-emerald-200">
                    Ticket ban gaya
                  </p>
                  <p className="mt-1 flex items-center gap-2 font-mono text-base font-semibold tracking-wide text-text-primary">
                    <Ticket className="h-4 w-4 text-emerald-300" />
                    {ticket.ticket_id}
                  </p>
                  <p className="mt-1.5 text-xs leading-5 text-text-secondary">
                    Status <span className="text-emerald-300">{ticket.status}</span>
                    {ticket.priority ? ` · Priority ${ticket.priority}` : ""}
                    {ticket.opening_date ? ` · ${ticket.opening_date}` : ""}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-text-secondary">
                    School ka staff jald rabta karega. Ye number sambhal kar
                    rakhein.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* ---- ghalti ---- */}
          {error && (
            <div className="mt-5 flex items-start gap-3 rounded-xl border border-red-400/30 bg-red-400/10 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
              <p className="text-sm leading-6 text-red-200">{error}</p>
            </div>
          )}

          <form className="mt-6 space-y-4" onSubmit={submit}>
            <label className="block">
              <span className="mb-2 block text-xs font-semibold tracking-wide text-text-secondary">
                Subject
              </span>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={140}
                disabled={sending}
                placeholder="e.g. Can’t start voice call"
                className="w-full rounded-xl border border-white/10 bg-bg-primary/30 px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-accent-primary/60 disabled:opacity-60"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-semibold tracking-wide text-text-secondary">
                Message
              </span>
              <textarea
                rows={6}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={5000}
                disabled={sending}
                placeholder="Describe your issue..."
                className="w-full resize-none rounded-xl border border-white/10 bg-bg-primary/30 px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-accent-primary/60 disabled:opacity-60"
              />
            </label>

            <motion.button
              whileHover={sending ? undefined : { y: -2 }}
              whileTap={sending ? undefined : { scale: 0.98 }}
              type="submit"
              disabled={sending}
              className="group relative w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="absolute -left-28 top-1/2 h-28 w-28 -translate-y-1/2 rotate-12 bg-accent-primary/40 blur-2xl transition-opacity group-hover:opacity-90" />
              <span className="absolute -right-28 top-1/2 h-28 w-28 -translate-y-1/2 -rotate-12 bg-accent-secondary/18 blur-2xl transition-opacity group-hover:opacity-90" />
              <span className="relative flex items-center justify-center gap-2">
                {sending && <Loader2 className="h-4 w-4 animate-spin" />}
                {sending ? "Bhej rahe hain…" : "Submit"}
              </span>
            </motion.button>
          </form>

          {/* ---- purane tickets ---- */}
          {!loadingList && tickets.length > 0 && (
            <div className="mt-8 border-t border-white/10 pt-6">
              <p className="mb-3 text-xs font-semibold tracking-wide text-text-secondary">
                YOUR TICKETS
              </p>
              <ul className="space-y-2">
                {tickets.map((t) => (
                  <li
                    key={t.name}
                    className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm text-text-primary">
                        {t.subject}
                      </p>
                      <p className="mt-0.5 font-mono text-xs text-text-secondary">
                        {t.name}
                        {t.opening_date ? ` · ${t.opening_date}` : ""}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                        t.status === "Closed" || t.status === "Resolved"
                          ? "bg-emerald-400/15 text-emerald-300"
                          : t.status === "On Hold"
                            ? "bg-amber-400/15 text-amber-300"
                            : "bg-cyan-400/15 text-cyan-300"
                      }`}
                    >
                      {t.status}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
