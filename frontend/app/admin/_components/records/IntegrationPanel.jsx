"use client";

/*
 * A school's records integration - the same panel for the school's admin
 * (Records page, their own school) and the platform's super admin
 * (Integrations page, any school).
 *
 *   status   where the records come from, whether it works, the last sync,
 *            how many records Vocira has, the last problem
 *   actions  Sync now, Test, Change system, Disconnect
 *   setup    what this kind of source needs: a connection form (ERPNext,
 *            Open School MIS, REST API, database), sheet links, Excel
 *            uploads - or nothing (Native Records)
 *   history  the recent syncs
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { PlugZap, RefreshCw, Repeat, Unplug } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Modal from "@/app/admin/_components/ui/Modal";
import { adminFetch, formatTime } from "@/app/admin/useAdminApi";

import ConnectionForm from "./ConnectionForm";
import ExcelUpload from "./ExcelUpload";
import ProviderPicker from "./ProviderPicker";
import SheetsLinks from "./SheetsLinks";
import SyncHistory from "./SyncHistory";
import { BUTTON, HUB, MODE_TEXT, RUN_LABEL, STATE_TEXT_CLASS, STATUS_BADGE, countsText, schoolPath, syncState } from "./shared";

export default function IntegrationPanel({ schoolId, superAdmin = false, onChanged, refreshKey = 0 }) {
  const detailPath = schoolId ? schoolPath(schoolId) : `${HUB}/mine`;
  const [detail, setDetail] = useState(null);
  const [catalogue, setCatalogue] = useState(null);
  const [view, setView] = useState("status"); // status | choose | setup
  const [pending, setPending] = useState(null); // a provider chosen but not saved yet
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [notice, setNotice] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [deleteRecords, setDeleteRecords] = useState(false);
  const polling = useRef(null);
  // Only the newest answer is shown: a slow load that started before a change
  // (connect, disconnect) must not put the old state back when it lands.
  const latest = useRef(0);

  const apply = useCallback((next) => {
    latest.current += 1;
    setDetail(next);
  }, []);

  const load = useCallback(async () => {
    const asked = ++latest.current;
    try {
      const next = await adminFetch(detailPath);
      if (asked === latest.current) setDetail(next);
      return next;
    } catch (err) {
      setProblem(err.message || "Could not load the records integration.");
      return null;
    }
  }, [detailPath]);

  useEffect(() => {
    load();
    adminFetch(`${HUB}/catalogue`).then(setCatalogue).catch((err) => setProblem(err.message));
    return () => clearInterval(polling.current);
  }, [load]);

  // records changed elsewhere on the page (Native Records): the counts here follow
  useEffect(() => {
    if (refreshKey) load();
  }, [refreshKey, load]);

  // While a sync runs, look again every few seconds until it is done.
  const watch = useCallback(() => {
    clearInterval(polling.current);
    let rounds = 0;
    polling.current = setInterval(async () => {
      rounds += 1;
      const next = await load();
      const running = next?.status?.running || next?.runs?.[0]?.status === "running";
      if (!running || rounds > 60) {
        clearInterval(polling.current);
        onChanged?.();
      }
    }, 2500);
  }, [load, onChanged]);

  const say = (text) => {
    setProblem("");
    setNotice(text);
    setTimeout(() => setNotice(""), 6000);
  };

  if (!detail || !catalogue) {
    return <Card><p className="text-xs text-text-secondary">{problem || "Loading the records integration…"}</p></Card>;
  }

  const actionsPath = schoolPath(detail.school.id);
  const status = detail.status;
  const provider = status.provider;
  const providers = catalogue.providers;
  const tables = catalogue.tables;
  const shown = view === "setup" && pending ? pending : provider;

  async function syncNow(trigger = "manual") {
    setBusy("sync");
    setProblem("");
    try {
      await adminFetch(`${actionsPath}/sync`, { method: "POST", body: JSON.stringify({ trigger }) });
      say("Sync started - the result shows below in a moment.");
      await load();
      watch();
    } catch (err) {
      setProblem(err.message || "Could not start a sync.");
    } finally {
      setBusy("");
    }
  }

  async function testSaved() {
    setBusy("test");
    setProblem("");
    setTestResult(null);
    try {
      const saved = detail.connection || {};
      const result = await adminFetch(`${actionsPath}/test`, {
        method: "POST",
        body: JSON.stringify({ kind: status.kind, settings: saved.settings || {}, secrets: {},
                               capabilities: saved.capabilities || [], allow_private_network: !!saved.allow_private_network }),
      });
      setTestResult(result);
      await load();
    } catch (err) {
      setProblem(err.message || "The test could not run.");
    } finally {
      setBusy("");
    }
  }

  async function choose(next) {
    if (next.fields.length) {
      // a system to sign in to: its form first, saved from there
      setPending(next);
      setView("setup");
      return;
    }
    if (!window.confirm(`Use ${next.label} for ${detail.school.name}'s records?`)) return;
    setBusy("choose");
    try {
      const chosen = await adminFetch(`${actionsPath}/connection`, {
        method: "PUT", body: JSON.stringify({ kind: next.kind, capabilities: next.capabilities.map((c) => c.key) }),
      });
      apply(chosen);
      setPending(null);
      setView("status");
      say(`${next.label} chosen.`);
      onChanged?.();
    } catch (err) {
      setProblem(err.message || "Could not choose it.");
    } finally {
      setBusy("");
    }
  }

  async function saved(next, text) {
    apply(next);
    setPending(null);
    setView("status");
    say(text);
    onChanged?.();
    if (next.status?.provider?.mode !== "native" && next.status?.provider?.setup !== "upload") {
      await syncNow("initial");
    }
  }

  async function disconnect() {
    setBusy("disconnect");
    try {
      const next = await adminFetch(`${actionsPath}/connection?delete_records=${deleteRecords ? "true" : "false"}`,
                                    { method: "DELETE" });
      apply(next);
      setConfirmDisconnect(false);
      setDeleteRecords(false);
      say("Disconnected - the school now answers general questions only.");
      onChanged?.();
    } catch (err) {
      setProblem(err.message || "Could not disconnect.");
    } finally {
      setBusy("");
    }
  }

  const health = !provider
    ? { label: "no records system", variant: "neutral" }
    : status.running
      ? { label: "syncing…", variant: "neutral" }
      : status.status === "error"
        ? { label: "not working", variant: "danger" }
        : status.status === "attention"
          ? { label: "needs attention", variant: "warning" }
          : status.connected
          ? { label: "connected", variant: "success" }
          : { label: "not connected yet", variant: "warning" };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1.5">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
              {detail.school.name} · records
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-lg font-semibold text-white">{provider ? provider.label : "General questions only"}</span>
              <Badge label={health.label} variant={health.variant} />
              {provider && STATUS_BADGE[provider.status] && (
                <Badge label={STATUS_BADGE[provider.status].label} variant={STATUS_BADGE[provider.status].variant} />
              )}
            </div>
            <p className="text-xs text-text-secondary">
              {provider ? MODE_TEXT[provider.mode] : "Connect a records system, or keep records in Vocira, so parents can ask about their own children."}
              {status.sync_minutes ? ` · re-read every ${status.sync_minutes} min` : ""}
            </p>
            <p className="text-xs text-white/90">{countsText(status.counts, tables)}</p>
            <p className="text-[11px] text-text-secondary">
              Last sync:{" "}
              {status.last_sync ? (
                <>
                  {formatTime(status.last_sync.at)} -{" "}
                  <span className={STATE_TEXT_CLASS[syncState(status.last_sync)]}>{RUN_LABEL[syncState(status.last_sync)]}</span>
                </>
              ) : "never"}
              {status.last_test ? ` · last test: ${formatTime(status.last_test.at)} - ${status.last_test.ok ? "ok" : "failed"}` : ""}
            </p>
            {status.last_error && (
              <p className="text-[11px] text-rose-200">
                Last problem ({formatTime(status.last_error.started_at)}): {status.last_error.error}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {provider && provider.mode !== "native" && provider.setup !== "upload" && (
              <Button onClick={() => syncNow("manual")} disabled={!!busy || status.running}>
                <RefreshCw className={`h-3.5 w-3.5 ${status.running ? "animate-spin" : ""}`} />
                {status.running ? "Syncing…" : "Sync now"}
              </Button>
            )}
            {provider && (
              <Button variant="outline" onClick={testSaved} disabled={!!busy}>
                <PlugZap className="h-3.5 w-3.5" />
                {busy === "test" ? "Testing…" : "Test"}
              </Button>
            )}
            {/* Which system a school's records come from is the platform super admin's choice */}
            {superAdmin && (
              <Button variant="outline" onClick={() => { setView(view === "choose" ? "status" : "choose"); setPending(null); }}>
                <Repeat className="h-3.5 w-3.5" />
                {provider ? "Change system" : "Choose a system"}
              </Button>
            )}
            {superAdmin && provider && (
              <Button variant="outline" onClick={() => setConfirmDisconnect(true)} disabled={!!busy}>
                <Unplug className="h-3.5 w-3.5" />
                Disconnect
              </Button>
            )}
          </div>
        </div>
        {notice && <p className="mt-3 text-xs text-emerald-200">{notice}</p>}
        {problem && <p className="mt-3 text-xs text-rose-300">{problem}</p>}
        {testResult && (
          <ul className={`mt-3 space-y-1 rounded-xl border p-3 text-xs ${testResult.ok ? "border-emerald-400/30" : "border-rose-400/30"}`}>
            {(testResult.steps || []).map((s, i) => (
              <li key={i}><span className={s.ok ? "text-emerald-300" : "text-rose-300"}>{s.ok ? "✓" : "✗"}</span>{" "}
                <span className="text-white">{s.name}</span> <span className="text-text-secondary">{s.detail}</span></li>
            ))}
          </ul>
        )}
      </Card>

      {superAdmin && view === "choose" && (
        <Card>
          <CardHeader title="Where do this school's records come from?"
                      description="Vocira reads only what the school allows, and only a parent's own children's records." />
          <ProviderPicker providers={providers} current={status.kind} onPick={choose} />
        </Card>
      )}

      {shown && view !== "choose" && (
        <Card>
          <CardHeader
            title={view === "setup" ? `Set up ${shown.label}` : "Setup"}
            // Native Records says it in its own words below, for each panel
            description={shown.setup === "native" ? undefined : shown.notes || shown.description}
          />
          {["connection", "rest", "database"].includes(shown.setup) && (
            <ConnectionForm key={shown.kind} path={actionsPath} provider={shown} saved={detail.connection}
                            tables={tables} superAdmin={superAdmin} onSaved={saved} />
          )}
          {shown.setup === "links" && (
            <SheetsLinks path={actionsPath} sheets={detail.sheets}
                         onChange={async (text) => { say(text); await load(); onChanged?.(); }} />
          )}
          {shown.setup === "upload" && (
            <ExcelUpload path={actionsPath} tables={tables.filter((t) => shown.tables.includes(t.table))}
                         onImported={async (text) => { say(text); await load(); onChanged?.(); }} />
          )}
          {shown.setup === "native" && (
            <p className="text-xs text-text-secondary">
              {superAdmin
                ? "The school's admin keeps these records on their Records page: students, parents, classes, teachers, attendance, fees, results, timetable and announcements."
                : "Add and edit the records below - one at a time, or a whole table from an Excel/CSV file. Vocira reads them as soon as they are saved."}
            </p>
          )}
          {view === "setup" && (
            <button type="button" className={`${BUTTON} mt-4`} onClick={() => { setView("status"); setPending(null); }}>
              Cancel
            </button>
          )}
        </Card>
      )}

      <Card>
        <CardHeader title="Sync history" description="Every sync, upload and test-run of the records - newest first." />
        <SyncHistory runs={detail.runs} tables={tables} />
      </Card>

      {confirmDisconnect && (
        <Modal id="disconnect-records" title={`Disconnect ${provider?.label}?`}
               description="Its settings and saved keys are deleted, and the school answers general questions only."
               onClose={() => setConfirmDisconnect(false)}>
          <label className="flex items-start gap-2 text-xs text-text-secondary">
            <input type="checkbox" className="mt-0.5" checked={deleteRecords} onChange={(e) => setDeleteRecords(e.target.checked)} />
            <span>Also delete the records Vocira has copied or kept for this school (students, attendance, fees …). This cannot be undone.</span>
          </label>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmDisconnect(false)}>Cancel</Button>
            <Button onClick={disconnect} disabled={busy === "disconnect"}>
              {busy === "disconnect" ? "Disconnecting…" : "Disconnect"}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
