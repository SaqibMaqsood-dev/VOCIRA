"use client";

/*
 * Google Sheets / online CSV: one live link per table. A link is read and
 * checked the moment it is pasted, kept only if it gives a usable sheet,
 * and re-read on the timer from then on. A broken edit leaves the last good
 * copy in use - the reason shows next to the table.
 */

import { useState } from "react";
import { Link2, Trash2 } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import { adminFetch, formatTime } from "@/app/admin/useAdminApi";

import { BUTTON, INPUT, keepEnter } from "./shared";

export default function SheetsLinks({ path, sheets, onChange }) {
  const [urls, setUrls] = useState({});
  const [busy, setBusy] = useState("");
  const [problems, setProblems] = useState({});

  async function link(table) {
    setBusy(table);
    setProblems({ ...problems, [table]: "" });
    try {
      const res = await adminFetch(`${path}/sheets/${table}`, { method: "PUT", body: JSON.stringify({ url: urls[table] || "" }) });
      setUrls({ ...urls, [table]: "" });
      onChange?.(`${table}: ${res.rows} rows linked.`);
    } catch (err) {
      setProblems({ ...problems, [table]: err.message || "Could not link it." });
    } finally {
      setBusy("");
    }
  }

  async function unlink(table) {
    if (!window.confirm(`Remove the ${table} link? Vocira stops reading this table.`)) return;
    setBusy(table);
    try {
      await adminFetch(`${path}/sheets/${table}`, { method: "DELETE" });
      onChange?.(`${table} link removed.`);
    } catch (err) {
      setProblems({ ...problems, [table]: err.message || "Could not remove it." });
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-3" onKeyDown={keepEnter}>
      <p className="text-[11px] text-text-secondary">
        Share each tab as &quot;Anyone with the link - Viewer&quot; and paste the tab&apos;s link. Re-read every{" "}
        {sheets?.sync_minutes || 5} minutes{sheets?.last_round_at ? ` - last round ${formatTime(sheets.last_round_at)}` : ""}.
      </p>
      {(sheets?.tables || []).map((t) => (
        <div key={t.table} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-semibold text-white">
              {t.label} {t.needed && <span className="text-rose-300">*</span>}
            </div>
            {t.link ? (
              <div className="flex items-center gap-2">
                <Badge label={t.link.last_error ? "using last good copy" : `${t.link.rows} rows`}
                       variant={t.link.last_error ? "warning" : "success"} />
                <span className="text-[10px] text-text-secondary">synced {formatTime(t.link.synced_at)}</span>
                <button type="button" className={BUTTON} onClick={() => unlink(t.table)} disabled={busy === t.table}>
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <Badge label="not linked" variant="neutral" />
            )}
          </div>
          <div className="mt-1 text-[10px] text-text-secondary/70">
            Columns: {t.required.join(", ")}
            {t.optional.length ? ` · optional: ${t.optional.join(", ")}` : ""}
          </div>
          {t.link?.last_error && <p className="mt-1 text-[11px] text-amber-200">{t.link.last_error}</p>}
          {(t.link?.warnings || []).map((w) => (
            <p key={w} className="mt-1 text-[11px] text-amber-200/80">{w}</p>
          ))}
          <div className="mt-2 flex gap-2">
            <input className={INPUT} placeholder={t.link ? "Paste a new link to replace it" : "https://docs.google.com/spreadsheets/d/…"}
                   value={urls[t.table] || ""} onChange={(e) => setUrls({ ...urls, [t.table]: e.target.value })} />
            <button type="button" className={BUTTON} onClick={() => link(t.table)}
                    disabled={busy === t.table || !(urls[t.table] || "").trim()}>
              <Link2 className="h-3.5 w-3.5" />
              {busy === t.table ? "Reading…" : "Link"}
            </button>
          </div>
          {problems[t.table] && <p className="mt-1 text-[11px] text-rose-300">{problems[t.table]}</p>}
        </div>
      ))}
    </div>
  );
}
