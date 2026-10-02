"use client";

/*
 * What the Records Integration Hub's screens share: the API's paths, the
 * form styles, and how a provider and a sync are described in words.
 * The hub itself is backend/.../services/integrations/.
 */

export const HUB = "/livekit/admin/integrations";
export const RECORDS = "/livekit/admin/records";

/** A school's integration endpoints - the super admin names one; a school's admin uses their own. */
export function schoolPath(schoolId) {
  return `${HUB}/schools/${encodeURIComponent(schoolId)}`;
}

export const INPUT =
  "w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none transition placeholder:text-text-secondary/50 focus:border-accent-primary/60";
export const SELECT = `${INPUT} [&>option]:bg-[#0b0a2a]`;
export const BUTTON =
  "inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/[0.12] disabled:opacity-50";
export const LABEL = "mb-1 block text-[11px] font-semibold text-text-secondary";

// How each way of connecting is described to the admin
export const MODE_TEXT = {
  live: "Read live from the school's system on each question",
  sync: "Copied into Vocira and kept up to date",
  native: "Kept in Vocira - managed on this page",
  unavailable: "Needs the vendor's official integration first",
};

export const STATUS_BADGE = {
  available: null,
  demo: { label: "optional · demo", variant: "neutral" },
  official_integration_required: { label: "official integration required", variant: "warning" },
};

export const RUN_BADGE = {
  success: "success",
  partial: "warning",
  failed: "danger",
  running: "neutral",
};

// A sync's outcome in words: part of it unreadable is not "ok"
export const RUN_LABEL = {
  success: "ok",
  partial: "needs attention",
  failed: "failed",
  running: "running…",
};

export const STATE_TEXT_CLASS = {
  success: "text-emerald-300",
  partial: "text-amber-300",
  failed: "text-rose-300",
};

/** The last sync's state, from a connection's last_sync. */
export function syncState(lastSync) {
  if (!lastSync) return null;
  return lastSync.state || (lastSync.ok ? "success" : "failed");
}

export const TRIGGER_TEXT = {
  initial: "First sync",
  manual: "Sync now",
  scheduled: "Scheduled",
  upload: "Upload",
  retry: "Retry",
};

/** "students: 312 · fees: 1,204" */
export function countsText(counts, tables) {
  const labels = Object.fromEntries((tables || []).map((t) => [t.table, t.label]));
  const parts = Object.entries(counts || {})
    .filter(([, n]) => n)
    .map(([t, n]) => `${labels[t] || t}: ${Number(n).toLocaleString()}`);
  return parts.length ? parts.join(" · ") : "no records yet";
}

export const keepEnter = (event) => {
  // Enter in a field must not submit a surrounding form by surprise
  if (event.key === "Enter" && event.target.tagName !== "TEXTAREA") event.preventDefault();
};
