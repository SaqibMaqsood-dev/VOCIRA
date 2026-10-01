"use client";

/*
 * A spreadsheet school's live records links - one per table (students,
 * attendance, results, fees): a Google Sheet tab or any online CSV /
 * Excel file. The server re-reads every link on its own timer - nobody
 * has to press anything - and on "Sync now"; a link that fails keeps the
 * last good copy in use, and the reason shows here. The box refreshes
 * itself, so the times it shows are always current. Students is the one that is needed: it links every
 * child to the guardian whose login (Accounts page) carries that ID.
 */

import { useCallback, useEffect, useState } from "react";
import { Link2, Pencil, RefreshCw, Trash2 } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import { adminFetch, formatTime } from "@/app/admin/useAdminApi";

const INPUT =
  "min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs text-white outline-none transition focus:border-accent-primary/60";

function host(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default function RecordsLinks({ schoolId, onChange }) {
  const [state, setState] = useState(null);
  const [drafts, setDrafts] = useState({});      // table -> link being typed
  const [editing, setEditing] = useState({});    // table -> changing its link
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [notice, setNotice] = useState(null);

  const path = `/livekit/admin/schools/${encodeURIComponent(schoolId)}/records`;

  const load = useCallback(async () => {
    try {
      setState(await adminFetch(path));
    } catch (err) {
      setProblem(err.message || "Could not read the records links.");
    }
  }, [path]);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  async function connect(table) {
    const url = (drafts[table.table] || "").trim();
    if (!url) return;
    setBusy(table.table);
    setProblem("");
    setNotice(null);
    try {
      const result = await adminFetch(`${path}/${table.table}/link`, {
        method: "PUT",
        body: JSON.stringify({ url }),
      });
      setNotice({
        text: `${table.label}: connected - ${result.link.rows} rows read from ${host(url)}.`,
        warnings: result.link.warnings || [],
      });
      setDrafts((d) => ({ ...d, [table.table]: "" }));
      setEditing((e) => ({ ...e, [table.table]: false }));
      await load();
      onChange?.();
    } catch (err) {
      setProblem(`${table.label}: ${err.message || "could not connect the link."}`);
    } finally {
      setBusy("");
    }
  }

  async function syncNow() {
    setBusy("sync");
    setProblem("");
    setNotice(null);
    try {
      const { results } = await adminFetch(`${path}/sync`, { method: "POST" });
      const failed = results.filter((r) => !r.ok);
      const changed = results.filter((r) => r.ok && r.changed).length;
      setNotice({
        text: results.length
          ? `Synced ${results.length - failed.length} of ${results.length} link(s)` +
            (changed ? ` - ${changed} had new data.` : " - no changes.")
          : "No links to sync yet.",
        warnings: failed.map((r) => `${r.table}: ${r.error}`),
      });
      await load();
      onChange?.();
    } catch (err) {
      setProblem(err.message || "Could not sync.");
    } finally {
      setBusy("");
    }
  }

  async function remove(table) {
    if (!window.confirm(`Disconnect the ${table.label} link? The agent stops answering from it.`)) return;
    setBusy(table.table);
    setProblem("");
    setNotice(null);
    try {
      await adminFetch(`${path}/${table.table}`, { method: "DELETE" });
      await load();
      onChange?.();
    } catch (err) {
      setProblem(err.message || "Could not disconnect the link.");
    } finally {
      setBusy("");
    }
  }

  const tables = state?.tables;
  const anyLinked = (tables || []).some((t) => t.link?.source_url);

  return (
    <div id="records-links" className="space-y-3 rounded-xl border border-white/10 bg-white/[0.03] p-4 sm:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-white">Live records links</p>
          <p className="mt-1 text-xs text-text-secondary">
            Paste the link of each table - a Google Sheet tab (Share → &quot;Anyone with the link&quot; → Viewer, then
            copy the link while that tab is open) or any online CSV / Excel file. If a link fails, the last good copy
            is kept. Students is needed - each row links a child to a Guardian ID, which a parent&apos;s login carries
            (Accounts page).
          </p>
          {state && (
            <p id="records-auto" className="mt-2 flex flex-wrap items-center gap-x-1.5 text-xs text-emerald-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>
                Auto-sync on - every {state.sync_minutes} minute{state.sync_minutes === 1 ? "" : "s"}, by itself.
              </span>
              {state.last_round_at && <span>Last check {formatTime(state.last_round_at)}.</span>}
              {state.next_round_at && <span>Next about {formatTime(state.next_round_at)}.</span>}
            </p>
          )}
        </div>
        <button
          id="records-sync-all"
          type="button"
          title="Not needed - links sync by themselves. Use it to bring a change in right away."
          onClick={syncNow}
          disabled={busy === "sync" || !anyLinked}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.06] px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-white/[0.12] disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${busy === "sync" ? "animate-spin" : ""}`} />
          {busy === "sync" ? "Syncing…" : "Sync now"}
        </button>
      </div>

      {problem && <p className="text-xs text-rose-300">{problem}</p>}
      {notice && (
        <div className="text-xs text-emerald-200">
          <p>{notice.text}</p>
          {notice.warnings.map((w) => (
            <p key={w} className="text-amber-200">
              {w}
            </p>
          ))}
        </div>
      )}

      {!tables ? (
        <p className="text-xs text-text-secondary">Loading…</p>
      ) : (
        <div className="divide-y divide-white/10">
          {tables.map((table) => {
            const link = table.link;
            const linked = !!link?.source_url;
            const showInput = !linked || editing[table.table];
            const failing = linked && link.last_error;
            return (
              <div key={table.table} id={`records-${table.table}`} className="space-y-2 py-3">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-[220px] flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white">{table.label}</span>
                      {table.needed && <Badge label="Needed" variant={link ? "success" : "warning"} />}
                      {failing && <Badge label="Sync failing" variant="danger" />}
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-text-secondary">
                      <span className="text-white/80">{table.required.join(", ")}</span>
                      {table.optional.length > 0 && <span> · optional: {table.optional.join(", ")}</span>}
                    </p>
                  </div>

                  {linked && (
                    <div className="min-w-[200px] text-xs" data-link>
                      <a
                        href={link.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-white hover:underline"
                        title={link.source_url}
                      >
                        <Link2 className="h-3 w-3" />
                        {host(link.source_url)}
                      </a>
                      <div className="text-text-secondary">
                        {link.rows} rows · checked {formatTime(link.last_attempt || link.synced_at)}
                      </div>
                    </div>
                  )}

                  {link && !linked && (
                    // a copy from before links (an uploaded file): in use, but never refreshed
                    <div className="min-w-[200px] text-xs" data-link>
                      <div className="text-white">Uploaded copy in use</div>
                      <div className="text-amber-200">{link.rows} rows · not live - connect a link below</div>
                    </div>
                  )}

                  {link && (
                    <div className="flex items-center gap-1.5">
                      {linked && (
                        <button
                          type="button"
                          onClick={() => setEditing((e) => ({ ...e, [table.table]: !e[table.table] }))}
                          className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:text-white"
                          title="Change link"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => remove(table)}
                        disabled={busy === table.table}
                        className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:border-rose-400/40 hover:text-rose-200 disabled:opacity-50"
                        title="Disconnect"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>

                {failing && (
                  <p className="text-[11px] text-rose-300">
                    Last check {formatTime(link.last_attempt)} failed: {link.last_error} Still answering from the copy
                    synced {formatTime(link.synced_at)}.
                  </p>
                )}

                {showInput && (
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      id={`records-link-${table.table}`}
                      type="url"
                      className={INPUT}
                      value={drafts[table.table] || ""}
                      onChange={(e) => setDrafts((d) => ({ ...d, [table.table]: e.target.value }))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          connect(table);
                        }
                      }}
                      placeholder="https://docs.google.com/spreadsheets/d/… or a link to a .csv / .xlsx file"
                    />
                    <button
                      id={`records-connect-${table.table}`}
                      type="button"
                      onClick={() => connect(table)}
                      disabled={busy === table.table || !(drafts[table.table] || "").trim()}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.06] px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-white/[0.12] disabled:opacity-50"
                    >
                      <Link2 className="h-3.5 w-3.5" />
                      {busy === table.table ? "Connecting…" : linked ? "Use this link" : "Connect"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
