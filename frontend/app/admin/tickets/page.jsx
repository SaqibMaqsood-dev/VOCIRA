"use client";

/*
 * Tickets - what parents sent from the Support page, for this school's
 * admin: a guardian's (from their account) and a guest's (from the school's
 * address). The admin answers here; a guardian reads the answer on their
 * Support page, a guest - who has no account - is answered by email.
 */

import { useMemo, useState } from "react";
import { Mail, RefreshCw } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import Modal from "@/app/admin/_components/ui/Modal";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";

const STATUSES = [
  { value: "open", label: "Open", variant: "warning" },
  { value: "in_progress", label: "In progress", variant: "neutral" },
  { value: "resolved", label: "Resolved", variant: "success" },
];
const STATUS_OF = Object.fromEntries(STATUSES.map((s) => [s.value, s]));

// a parent waiting on an answer - a new ticket should not sit unseen for long
const POLL_MS = 20000;

const INPUT =
  "w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none transition focus:border-accent-primary/60";

export default function TicketsPage() {
  const { data: tickets, loading, error, reload } = useAdminData("/livekit/admin/tickets?limit=200", [], {
    pollMs: POLL_MS,
  });
  const [filter, setFilter] = useState("all");
  const [openId, setOpenId] = useState(null);
  const [draft, setDraft] = useState({ status: "open", reply: "" });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [notice, setNotice] = useState("");

  const counts = useMemo(() => {
    const c = { all: tickets.length };
    for (const s of STATUSES) c[s.value] = tickets.filter((t) => t.status === s.value).length;
    return c;
  }, [tickets]);
  const visible = filter === "all" ? tickets : tickets.filter((t) => t.status === filter);
  const ticket = openId ? tickets.find((t) => t.id === openId) : null;

  function open(t) {
    setOpenId(t.id);
    setDraft({ status: t.status, reply: t.reply || "" });
    setProblem("");
  }

  function close() {
    setOpenId(null);
    setProblem("");
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setProblem("");
    try {
      const saved = await adminFetch(`/livekit/admin/tickets/${encodeURIComponent(ticket.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: draft.status, reply: draft.reply }),
      });
      setOpenId(null);
      setNotice(`${saved.reference} is saved - ${STATUS_OF[saved.status]?.label || saved.status}.`);
      setTimeout(() => setNotice(""), 5000);
      reload({ silent: true });
    } catch (err) {
      setProblem(err.message || "Could not save the ticket.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <FullScreenLoader label="Loading tickets…" subLabel="Fetching what parents sent from Support" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Tickets</h1>
          <p className="mt-1 text-xs text-text-secondary">
            What parents and guests sent from the Support page. Answer them here.
          </p>
        </div>
        <Button variant="outline" onClick={() => reload()}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">{error}</div>
      )}

      {/* which tickets: every one, or one state */}
      <div id="ticket-filters" className="flex flex-wrap gap-2">
        {[{ value: "all", label: "All" }, ...STATUSES].map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
              filter === f.value
                ? "border-accent-primary/50 bg-accent-primary/20 text-white"
                : "border-white/10 bg-white/[0.04] text-text-secondary hover:text-white"
            }`}
          >
            {f.label} ({counts[f.value] || 0})
          </button>
        ))}
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Ticket</TH>
            <TH>From</TH>
            <TH>Status</TH>
            <TH>Received</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {visible.length === 0 && !error && (
            <TR>
              <TD colSpan={5} className="py-6 text-center text-xs text-text-secondary">
                {tickets.length === 0 ? "No tickets yet - nobody has written in from the Support page." : "No tickets here."}
              </TD>
            </TR>
          )}

          {visible.map((t) => (
            <TR key={t.id}>
              <TD className="max-w-md">
                <div className="truncate text-xs font-medium text-white">{t.subject}</div>
                <div className="mt-0.5 font-mono text-[11px] text-text-secondary">{t.reference}</div>
              </TD>
              <TD>
                <div className="text-xs text-white">{t.name || "Guest"}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-text-secondary">
                  <span className="truncate">{t.email}</span>
                  <Badge label={t.from === "guardian" ? "Guardian" : "Guest"} variant="neutral" />
                </div>
              </TD>
              <TD>
                <Badge label={STATUS_OF[t.status]?.label || t.status} variant={STATUS_OF[t.status]?.variant || "neutral"} />
                {t.reply && <div className="mt-1 text-[10px] text-text-secondary">answered</div>}
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">{formatTime(t.createdAt)}</TD>
              <TD className="whitespace-nowrap text-right">
                <Button variant="outline" onClick={() => open(t)} aria-label={`Open ${t.reference}`}>
                  View
                </Button>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {ticket && (
        <Modal
          id="ticket-dialog"
          size="lg"
          title={`${ticket.reference} · ${ticket.subject}`}
          description={`From ${ticket.name || "a guest"} <${ticket.email}> · ${formatTime(ticket.createdAt)}`}
          onClose={close}
        >
          {problem && (
            <div className="mb-3 rounded-xl border border-red-400/30 bg-red-400/[0.07] px-3 py-2 text-xs text-red-200">{problem}</div>
          )}
          <div className="mb-4">
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Message</p>
            <p id="ticket-message" className="whitespace-pre-line rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm leading-6 text-white">
              {ticket.message || "(no message - only the subject)"}
            </p>
          </div>

          <form onSubmit={save} className="space-y-3">
            <label className="block space-y-1 text-xs text-text-secondary">
              <span>Your reply</span>
              <textarea
                id="ticket-reply"
                rows={5}
                maxLength={5000}
                className={`${INPUT} resize-none`}
                value={draft.reply}
                onChange={(e) => setDraft({ ...draft, reply: e.target.value })}
                placeholder="Write your answer to the parent…"
              />
              <span className="block text-[11px] text-text-secondary/80">
                {ticket.from === "guardian"
                  ? "The guardian sees this on their Support page, under Your tickets."
                  : "A guest has no account to see it - answer them by email as well."}
              </span>
            </label>

            <div className="flex flex-wrap items-end gap-3">
              <label className="space-y-1 text-xs text-text-secondary">
                <span>Status</span>
                <select
                  id="ticket-status"
                  className={INPUT}
                  style={{ colorScheme: "dark" }}
                  value={draft.status}
                  onChange={(e) => setDraft({ ...draft, status: e.target.value })}
                >
                  {STATUSES.map((s) => (
                    <option key={s.value} value={s.value} style={{ backgroundColor: "#100944" }}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="ml-auto flex flex-wrap gap-2">
                <a
                  href={`mailto:${ticket.email}?subject=${encodeURIComponent(`Re: ${ticket.reference} ${ticket.subject}`)}&body=${encodeURIComponent(draft.reply)}`}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 px-3 py-2 text-xs text-text-secondary hover:text-white"
                >
                  <Mail className="h-3.5 w-3.5" />
                  Email
                </a>
                <Button variant="outline" type="button" onClick={close}>
                  Cancel
                </Button>
                <Button type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Save"}
                </Button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {notice && (
        <div
          id="tickets-notice"
          role="status"
          className="fixed bottom-6 right-6 z-[95] max-w-sm rounded-xl border border-emerald-400/30 bg-bg-secondary px-4 py-3 text-xs text-emerald-200 shadow-card"
        >
          {notice}
        </div>
      )}
    </div>
  );
}
