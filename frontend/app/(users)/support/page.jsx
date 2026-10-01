"use client";

/**
 * Support page.
 *
 * A ticket goes to the parent's own school: its admin finds it on the
 * panel's Tickets page and can answer it there. A guardian's school is
 * their account's; a guest's is the school whose address this page is on.
 *
 * (Tickets used to go to the first school's ERPNext, whatever school the
 * parent was from - another school saw them, and their own never did.)
 */

import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Loader2, MessageSquareReply, Ticket } from "lucide-react";
import { useEffect, useState } from "react";
import { authFetch, getAccessToken } from "@/lib/session";
import { useSchoolOfPage, useSite } from "@/lib/site";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function SupportPage() {
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const [sending, setSending] = useState(false);
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState(null);

  const [tickets, setTickets] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  // tickets resolved over 30 days ago wait behind "Show older tickets"
  const [showOlder, setShowOlder] = useState(false);
  const currentTickets = tickets.filter((t) => !t.older);
  const olderTickets = tickets.filter((t) => t.older);

  // The token has to be held in state: there is no localStorage on
  // the server, so the first render only ever sees null. Reading it
  // directly causes a React hydration mismatch.
  const [token, setToken] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    setToken(getAccessToken());
    setAuthChecked(true);
  }, []);

  const loggedIn = Boolean(token);

  // A guest's ticket goes to the school whose address this page is on -
  // with no school here, it would have nowhere to go.
  const site = useSite();
  const school = useSchoolOfPage(site?.subdomain);
  const guestWithoutSchool = authChecked && !loggedIn && site !== null && (!site.subdomain || school === null);

  // ---- pehle ke tickets ----
  const loadTickets = async () => {
    if (!token || !API_URL) {
      setLoadingList(false);
      return;
    }

    try {
      // authFetch renews an expired access token and retries, so a
      // parent who left the tab open still sees their tickets.
      const res = await authFetch("/livekit/support/tickets");

      if (res.ok) {
        const rows = await res.json();
        setTickets(Array.isArray(rows) ? rows : []);
      }
    } catch {
      // if the list fails to load, the form must still work
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    if (!authChecked) return;
    loadTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authChecked, token]);

  const submit = async (e) => {
    e.preventDefault();

    setError(null);
    setTicket(null);

    if (!API_URL) {
      setError("API URL is not configured (NEXT_PUBLIC_API_URL).");
      return;
    }

    if (!loggedIn && !email.trim()) {
      setError("Please enter your email address so we can reply.");
      return;
    }

    if (subject.trim().length < 3) {
      setError("Subject must be at least 3 characters.");
      return;
    }

    setSending(true);

    try {
      // A logged-in parent goes through authFetch, which attaches
      // the token and renews it if it has expired. A guest has no
      // token at all, and the endpoint accepts that - so plain fetch
      // is right there.
      const body = JSON.stringify(
        loggedIn
          ? { subject, message }
          : { subject, message, email, school: school?.id }
      );

      const res = loggedIn
        ? await authFetch("/livekit/support/tickets", {
            method: "POST",
            body,
          })
        : await fetch(`${API_URL}/livekit/support/tickets`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body,
          });

      if (res.status === 401) {
        setError("Your session has expired. Please log in again.");
        return;
      }

      if (!res.ok) {
        // Show the backend's real reason, not one of our own making
        let detail = `Could not create the ticket (HTTP ${res.status}).`;
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
      setEmail("");
      loadTickets();
    } catch {
      setError(
        "Could not reach the server. Please make sure the API Gateway is running."
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page-shell flex items-start justify-center">
      {/* overflow-hidden because the two blurs below sit outside
          this box on purpose - without it they widen the page. */}
      <div className="relative w-full max-w-xl overflow-hidden">
        <div className="pointer-events-none absolute -left-20 top-10 size-56 animate-floaty rounded-full bg-accent-primary/14 blur-3xl" />
        <div className="pointer-events-none absolute -right-20 top-36 size-64 animate-floaty rounded-full bg-accent-secondary/10 blur-3xl [animation-delay:900ms]" />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="glass relative p-5 sm:p-8"
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
                    Ticket created
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
                    {loggedIn
                      ? "Your school's staff will reply here, under Your tickets. Please keep this reference number."
                      : "Your school's staff will contact you at your email. Please keep this reference number."}
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

          {guestWithoutSchool && (
            <div id="support-no-school" className="mt-5 flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
              <p className="text-sm leading-6 text-amber-100">
                Open this page from your school&apos;s own address - the link your school shares - so your
                message reaches your school.
              </p>
            </div>
          )}

          <form className="mt-6 space-y-4" onSubmit={submit}>
            {/*
              The email is asked for only when not logged in. A
              logged-in parent's email comes from their account -
              asking again is redundant, and the backend ignores the
              email in the request anyway (otherwise anyone could
              open a ticket in someone else's name).
            */}
            {authChecked && !loggedIn && (
              <label className="block">
                <span className="mb-2 block text-xs font-semibold tracking-wide text-text-secondary">
                  Email
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={sending}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-white/10 bg-bg-primary/30 px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-accent-primary/60 disabled:opacity-60"
                />
                <span className="mt-1.5 block text-xs leading-5 text-text-secondary">
                  We will reply to this address.{" "}
                  <a
                    href="/login"
                    className="text-accent-secondary underline decoration-dotted hover:opacity-80"
                  >
                    Log in
                  </a>{" "}
                  to track your tickets.
                </span>
              </label>
            )}

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
              disabled={sending || guestWithoutSchool}
              className="group relative w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="absolute -left-28 top-1/2 h-28 w-28 -translate-y-1/2 rotate-12 bg-accent-primary/40 blur-2xl transition-opacity group-hover:opacity-90" />
              <span className="absolute -right-28 top-1/2 h-28 w-28 -translate-y-1/2 -rotate-12 bg-accent-secondary/18 blur-2xl transition-opacity group-hover:opacity-90" />
              <span className="relative flex items-center justify-center gap-2">
                {sending && <Loader2 className="h-4 w-4 animate-spin" />}
                {sending ? "Submitting…" : "Submit"}
              </span>
            </motion.button>
          </form>

          {/* ---- purane tickets ---- */}
          {!loadingList && tickets.length > 0 && (
            <div id="your-tickets" className="mt-8 border-t border-white/10 pt-6">
              <p className="text-xs font-semibold tracking-wide text-text-secondary">
                YOUR TICKETS
              </p>
              <p className="mb-3 mt-1 text-[11px] text-text-secondary/70">
                Open tickets stay at the top. A resolved one moves to older tickets 30 days after it was resolved.
              </p>
              <ul className="space-y-2">
                {[...currentTickets, ...(showOlder ? olderTickets : [])].map((t) => (
                  <li
                    key={t.name}
                    className="support-ticket rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm text-text-primary">
                          {t.subject}
                        </p>
                        <p className="mt-0.5 font-mono text-xs text-text-secondary">
                          {t.name}
                          {t.opening_date ? ` · ${t.opening_date}` : ""}
                          {t.resolved_date ? ` · resolved ${t.resolved_date}` : ""}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                          t.status === "Resolved"
                            ? "bg-emerald-400/15 text-emerald-300"
                            : t.status === "In progress"
                              ? "bg-amber-400/15 text-amber-300"
                              : "bg-cyan-400/15 text-cyan-300"
                        }`}
                      >
                        {t.status}
                      </span>
                    </div>
                    {/* the school's answer */}
                    {t.reply && (
                      <div className="mt-3 flex items-start gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2">
                        <MessageSquareReply className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-secondary" />
                        <p className="whitespace-pre-line text-xs leading-5 text-text-primary">{t.reply}</p>
                      </div>
                    )}
                  </li>
                ))}
              </ul>

              {currentTickets.length === 0 && !showOlder && (
                <p className="text-xs text-text-secondary">No open or recent tickets.</p>
              )}

              {olderTickets.length > 0 && (
                <button
                  id="toggle-older-tickets"
                  type="button"
                  onClick={() => setShowOlder((shown) => !shown)}
                  className="mt-3 text-xs font-medium text-accent-secondary underline decoration-dotted hover:opacity-80"
                >
                  {showOlder ? "Hide older tickets" : `Show older tickets (${olderTickets.length})`}
                </button>
              )}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
