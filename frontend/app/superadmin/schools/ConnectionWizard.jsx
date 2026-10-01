"use client";

/*
 * Connecting a school to its records system (ERPNext, Open School MIS,
 * ...). The form is built from what the system needs (the catalogue
 * from /livekit/admin/connectors): its fields - secret ones are stored
 * encrypted and never shown again, only whether they are set - then
 * Test connection, what Vocira may read, Save & connect, Disconnect,
 * and the history of who did what.
 */

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Link2, PlugZap, Trash2, XCircle } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import { adminFetch, formatTime } from "@/app/admin/useAdminApi";

const INPUT =
  "w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none transition focus:border-accent-primary/60";
const BUTTON =
  "inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/[0.12] disabled:opacity-50";

const keepEnter = (event) => {
  // inside the school's own form: Enter must not save the school
  if (event.key === "Enter") event.preventDefault();
};

export default function ConnectionWizard({ schoolId, spec, onChange }) {
  const path = `/livekit/admin/schools/${encodeURIComponent(schoolId)}/connection`;
  const [view, setView] = useState(undefined); // undefined: loading; null: not connected
  const [settings, setSettings] = useState({});
  const [secrets, setSecrets] = useState({});
  const [caps, setCaps] = useState(spec.capabilities.map((c) => c.key));
  const [allowPrivate, setAllowPrivate] = useState(false);
  const [test, setTest] = useState(null);
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      const { connection } = await adminFetch(path);
      setView(connection);
      if (connection && connection.kind === spec.kind) {
        setSettings(connection.settings || {});
        setCaps(connection.capabilities || []);
        setAllowPrivate(!!connection.allow_private_network);
      }
    } catch (err) {
      setProblem(err.message || "Could not read the connection.");
      setView(null);
    }
  }, [path, spec.kind]);

  useEffect(() => {
    load();
  }, [load]);

  const connected = view && view.kind === spec.kind;
  const savedSecrets = connected ? view.secrets_set || [] : [];

  const body = () =>
    JSON.stringify({
      kind: spec.kind,
      settings,
      secrets,
      capabilities: caps,
      allow_private_network: allowPrivate,
    });

  async function runTest() {
    setBusy("test");
    setProblem("");
    setNotice("");
    setTest(null);
    try {
      const result = await adminFetch(`${path}/test`, { method: "POST", body: body() });
      setTest(result);
      if (result.ok && !connected) {
        // first connection: tick what the system turned out to give
        setCaps(spec.capabilities.map((c) => c.key).filter((key) => result.capabilities.includes(key)));
      }
      await load();
    } catch (err) {
      setProblem(err.message || "Could not test the connection.");
    } finally {
      setBusy("");
    }
  }

  async function save() {
    setBusy("save");
    setProblem("");
    setNotice("");
    try {
      await adminFetch(path, { method: "PUT", body: body() });
      setSecrets({});
      setNotice(`${spec.label} connected. The agent reads it live from now on.`);
      await load();
      onChange?.();
    } catch (err) {
      setProblem(err.message || "Could not save the connection.");
    } finally {
      setBusy("");
    }
  }

  async function disconnect() {
    if (!window.confirm(`Disconnect ${spec.label}? Its settings and keys are deleted and the school answers general questions only.`)) return;
    setBusy("disconnect");
    setProblem("");
    setNotice("");
    try {
      await adminFetch(path, { method: "DELETE" });
      setTest(null);
      setSecrets({});
      setNotice("Disconnected - the keys are deleted.");
      await load();
      onChange?.();
    } catch (err) {
      setProblem(err.message || "Could not disconnect.");
    } finally {
      setBusy("");
    }
  }

  if (view === undefined) {
    return <p className="text-xs text-text-secondary sm:col-span-2">Loading the connection…</p>;
  }

  return (
    <div id="connection-wizard" className="space-y-4 rounded-xl border border-white/10 bg-white/[0.03] p-4 sm:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white">Connect {spec.label}</p>
          <p className="mt-1 text-xs text-text-secondary">{spec.description}</p>
        </div>
        <span id="connection-status">
          {connected ? (
            view.last_test?.ok === false ? (
              <Badge label="Connected · last test failed" variant="danger" />
            ) : (
              <Badge label="Connected" variant="success" />
            )
          ) : (
            <Badge label="Not connected" variant="warning" />
          )}
        </span>
      </div>

      {problem && <p className="text-xs text-rose-300">{problem}</p>}
      {notice && <p className="text-xs text-emerald-200">{notice}</p>}

      <div className="grid gap-3 sm:grid-cols-2">
        {spec.fields.map((f) => {
          const isSecret = f.kind === "secret";
          const saved = isSecret && savedSecrets.includes(f.key);
          return (
            <label key={f.key} className="space-y-1 text-xs text-text-secondary">
              <span>{f.label}</span>
              <input
                id={`conn-${f.key}`}
                type={isSecret ? "password" : f.kind === "email" ? "email" : "text"}
                autoComplete={isSecret ? "new-password" : "off"}
                className={INPUT}
                value={(isSecret ? secrets[f.key] : settings[f.key]) || ""}
                placeholder={saved ? "•••••• saved - leave empty to keep it" : f.placeholder}
                onChange={(e) =>
                  isSecret
                    ? setSecrets({ ...secrets, [f.key]: e.target.value })
                    : setSettings({ ...settings, [f.key]: e.target.value })
                }
                onKeyDown={keepEnter}
              />
              {f.help && <span className="block text-[11px] text-text-secondary/80">{f.help}</span>}
            </label>
          );
        })}
      </div>

      <label className="flex items-start gap-2 text-xs text-text-secondary">
        <input
          id="conn-private"
          type="checkbox"
          checked={allowPrivate}
          onChange={(e) => setAllowPrivate(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          This system runs on the school&apos;s own network (allow a local address such as localhost or 192.168.x.x).
          Leave it off for systems on the internet.
        </span>
      </label>

      <div className="space-y-2">
        <button id="conn-test" type="button" onClick={runTest} disabled={!!busy} className={BUTTON}>
          <PlugZap className="h-3.5 w-3.5" />
          {busy === "test" ? "Testing…" : "Test connection"}
        </button>
        {test && (
          <ul id="conn-test-result" className="space-y-1 text-xs">
            {test.steps.map((s) => (
              <li key={s.name} className={`flex items-start gap-1.5 ${s.ok ? "text-emerald-200" : "text-rose-300"}`}>
                {s.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                <span>
                  <span className="font-medium">{s.name}</span>
                  {s.detail ? ` - ${s.detail}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-1">
        <p className="text-xs text-text-secondary">What Vocira may read (parents ask about these on calls):</p>
        <div className="flex flex-wrap gap-3">
          {spec.capabilities.map((c) => (
            <label key={c.key} className="flex items-center gap-1.5 text-xs text-white">
              <input
                id={`conn-cap-${c.key}`}
                type="checkbox"
                checked={caps.includes(c.key)}
                onChange={(e) => setCaps(e.target.checked ? [...caps, c.key] : caps.filter((k) => k !== c.key))}
              />
              {c.label}
            </label>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button id="conn-save" type="button" onClick={save} disabled={!!busy} className={`${BUTTON} bg-accent-primary/80 hover:bg-accent-primary`}>
          <Link2 className="h-3.5 w-3.5" />
          {busy === "save" ? "Saving…" : connected ? "Save changes to the connection" : "Save & connect"}
        </button>
        {connected && (
          <button
            id="conn-disconnect"
            type="button"
            onClick={disconnect}
            disabled={!!busy}
            className={`${BUTTON} hover:border-rose-400/40 hover:text-rose-200`}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Disconnect
          </button>
        )}
        {connected && view.last_test && (
          <span className="text-[11px] text-text-secondary">
            Last test {formatTime(view.last_test.at)}: {view.last_test.ok ? "worked" : "failed"}
          </span>
        )}
      </div>

      {view?.audit?.length > 0 && (
        <div id="conn-history" className="space-y-1 border-t border-white/10 pt-3">
          <p className="text-[11px] uppercase tracking-wider text-text-secondary">History</p>
          {view.audit.map((a, i) => (
            <p key={i} className="text-[11px] text-text-secondary">
              {formatTime(a.at)} · <span className="text-white">{a.action}</span> by {a.actor || "?"}
              {a.detail ? ` - ${a.detail}` : ""}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
