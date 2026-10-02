"use client";

/*
 * Connecting a system that is signed in to: ERPNext, Open School MIS, a
 * Generic REST API or a read-only database.
 *
 * The form is built from the provider's fields (the catalogue). A secret is
 * never shown again once saved - the field only says it is saved, and left
 * empty keeps it. A REST API gets an endpoint per table, a database a SELECT
 * per table; after a test, each table's columns can be mapped to Vocira's
 * fields. Only the platform's super admin may allow a system on the
 * school's own network.
 */

import { useState } from "react";
import { CheckCircle2, PlugZap, Save, XCircle } from "lucide-react";

import { adminFetch } from "@/app/admin/useAdminApi";

import MappingEditor from "./MappingEditor";
import { BUTTON, INPUT, LABEL, SELECT, keepEnter } from "./shared";

const SYNC_OPTIONS = [
  [15, "every 15 minutes"],
  [30, "every 30 minutes"],
  [60, "every hour"],
  [180, "every 3 hours"],
  [360, "every 6 hours"],
  [1440, "once a day"],
];

export default function ConnectionForm({ path, provider, saved, tables, superAdmin, onSaved }) {
  const mine = saved && saved.kind === provider.kind ? saved : null;
  const defaults = Object.fromEntries(
    provider.fields.filter((f) => f.kind === "select" && f.options.length).map((f) => [f.key, f.options[0][0]])
  );
  const [settings, setSettings] = useState({ ...defaults, ...(mine?.settings || {}) });
  const [secrets, setSecrets] = useState({});
  const [caps, setCaps] = useState(mine?.capabilities?.length ? mine.capabilities : provider.capabilities.map((c) => c.key));
  const [allowPrivate, setAllowPrivate] = useState(!!mine?.allow_private_network);
  const [syncMinutes, setSyncMinutes] = useState(mine?.sync_minutes || provider.sync_minutes || 60);
  const [mapping, setMapping] = useState(mine?.mapping || {});
  const [test, setTest] = useState(null);
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");

  const perTable = provider.setup === "rest" ? "endpoints" : provider.setup === "database" ? "queries" : null;
  const savedSecrets = mine?.secrets_set || [];
  const byName = Object.fromEntries((tables || []).map((t) => [t.table, t]));

  function body() {
    return {
      kind: provider.kind,
      settings,
      secrets,
      capabilities: caps,
      allow_private_network: allowPrivate,
      ...(perTable ? { sync_minutes: Number(syncMinutes), mapping } : {}),
    };
  }

  async function runTest() {
    setBusy("test");
    setProblem("");
    try {
      const result = await adminFetch(`${path}/test`, { method: "POST", body: JSON.stringify(body()) });
      setTest(result);
      // fill each table's mapping with Vocira's suggestion where the admin chose nothing yet
      if (result.suggested) {
        const next = { ...mapping };
        Object.entries(result.suggested).forEach(([table, suggestion]) => {
          next[table] = { ...Object.fromEntries(Object.entries(suggestion).filter(([, v]) => v)), ...(next[table] || {}) };
        });
        setMapping(next);
      }
    } catch (err) {
      setProblem(err.message || "The test could not run.");
    } finally {
      setBusy("");
    }
  }

  async function save() {
    setBusy("save");
    setProblem("");
    try {
      const detail = await adminFetch(`${path}/connection`, { method: "PUT", body: JSON.stringify(body()) });
      setSecrets({});
      onSaved?.(detail, `${provider.label} saved.`);
    } catch (err) {
      setProblem(err.message || "Could not save.");
    } finally {
      setBusy("");
    }
  }

  const setTableValue = (table, key, value) => {
    const all = { ...(settings[perTable] || {}) };
    if (perTable === "endpoints") {
      all[table] = { ...(all[table] || {}), [key]: value };
    } else {
      all[table] = value;
    }
    setSettings({ ...settings, [perTable]: all });
  };

  return (
    <div className="space-y-5" onKeyDown={keepEnter}>
      <div className="grid gap-3 sm:grid-cols-2">
        {provider.fields.map((field) => {
          if (field.key === "auth_header" && settings.auth_type !== "header") return null;
          if (field.key === "username" && provider.setup === "rest" && settings.auth_type !== "basic") return null;
          if (field.key === "token" && settings.auth_type === "none") return null;
          const isSecret = field.kind === "secret";
          return (
            <label key={field.key} className="block min-w-0">
              <span className={LABEL}>
                {field.label}
                {field.required && !isSecret ? <span className="text-rose-300"> *</span> : null}
              </span>
              {field.kind === "select" ? (
                <select
                  className={SELECT}
                  value={settings[field.key] || ""}
                  onChange={(e) => setSettings({ ...settings, [field.key]: e.target.value })}
                >
                  {field.options.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className={INPUT}
                  type={isSecret ? "password" : field.kind === "number" ? "number" : field.kind === "email" ? "email" : "text"}
                  autoComplete={isSecret ? "new-password" : "off"}
                  value={isSecret ? secrets[field.key] || "" : settings[field.key] || ""}
                  placeholder={isSecret && savedSecrets.includes(field.key) ? "•••••• saved - leave empty to keep it" : field.placeholder}
                  onChange={(e) =>
                    isSecret
                      ? setSecrets({ ...secrets, [field.key]: e.target.value })
                      : setSettings({ ...settings, [field.key]: e.target.value })
                  }
                />
              )}
              {field.help && <span className="mt-1 block text-[10px] text-text-secondary/70">{field.help}</span>}
            </label>
          );
        })}
      </div>

      {perTable && (
        <div className="space-y-2">
          <div className={LABEL}>
            {perTable === "endpoints"
              ? "Endpoints - from the vendor's documentation (GET only). Students is needed."
              : "One SELECT per table - only reading is allowed. Students is needed."}
          </div>
          {provider.tables.map((table) => (
            <div key={table} className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-3 sm:grid-cols-[120px_1fr]">
              <div className="pt-2 text-xs font-semibold text-white">
                {byName[table]?.label || table}
                {table === "students" ? <span className="text-rose-300"> *</span> : null}
              </div>
              {perTable === "endpoints" ? (
                <div className="grid gap-2 sm:grid-cols-3">
                  <input className={INPUT} placeholder="/students" value={settings.endpoints?.[table]?.path || ""}
                         onChange={(e) => setTableValue(table, "path", e.target.value)} />
                  <input className={INPUT} placeholder="list path, e.g. data.items" value={settings.endpoints?.[table]?.list_path || ""}
                         onChange={(e) => setTableValue(table, "list_path", e.target.value)} />
                  <input className={INPUT} placeholder="next page, e.g. links.next" value={settings.endpoints?.[table]?.next_path || ""}
                         onChange={(e) => setTableValue(table, "next_path", e.target.value)} />
                </div>
              ) : (
                <textarea className={`${INPUT} font-mono text-xs`} rows={2}
                          placeholder={`SELECT ... FROM ${table}`} value={settings.queries?.[table] || ""}
                          onChange={(e) => setTableValue(table, null, e.target.value)} />
              )}
            </div>
          ))}
          <label className="block max-w-xs">
            <span className={LABEL}>Read it again</span>
            <select className={SELECT} value={syncMinutes} onChange={(e) => setSyncMinutes(e.target.value)}>
              {SYNC_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      <div>
        <div className={LABEL}>What Vocira may read (parents ask about these on calls)</div>
        <div className="flex flex-wrap gap-3">
          {provider.capabilities.map((c) => (
            <label key={c.key} className="inline-flex items-center gap-1.5 text-xs text-white">
              <input
                type="checkbox"
                checked={caps.includes(c.key)}
                onChange={(e) => setCaps(e.target.checked ? [...caps, c.key] : caps.filter((x) => x !== c.key))}
              />
              {c.label}
            </label>
          ))}
        </div>
      </div>

      {superAdmin && provider.fields.length > 0 && (
        <label className="flex items-start gap-2 text-xs text-text-secondary">
          <input type="checkbox" className="mt-0.5" checked={allowPrivate} onChange={(e) => setAllowPrivate(e.target.checked)} />
          <span>
            This system runs on the school&apos;s own network (allow a local address such as localhost or 192.168.x.x).
            Leave it off for systems on the internet.
          </span>
        </label>
      )}

      {problem && <p className="text-xs text-rose-300">{problem}</p>}

      <div className="flex flex-wrap gap-2">
        <button type="button" className={BUTTON} onClick={runTest} disabled={!!busy}>
          <PlugZap className="h-3.5 w-3.5" />
          {busy === "test" ? "Testing…" : "Test connection"}
        </button>
        <button type="button" className={`${BUTTON} border-accent-primary/50 bg-accent-primary/80 hover:bg-accent-primary`}
                onClick={save} disabled={!!busy}>
          <Save className="h-3.5 w-3.5" />
          {busy === "save" ? "Saving…" : mine ? "Save changes" : "Save & connect"}
        </button>
      </div>

      {test && (
        <div className={`rounded-xl border p-3 ${test.ok ? "border-emerald-400/30 bg-emerald-400/[0.06]" : "border-rose-400/30 bg-rose-400/[0.06]"}`}>
          <ul className="space-y-1 text-xs">
            {(test.steps || []).map((step, i) => (
              <li key={i} className="flex items-start gap-1.5">
                {step.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300" />
                  : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-300" />}
                <span className="text-white">{step.name}</span>
                <span className="text-text-secondary">{step.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {perTable && test?.columns && Object.keys(test.columns).length > 0 && (
        <div className="space-y-4">
          <div className={LABEL}>Map the columns - Vocira filled in what it recognised. Saved with the connection.</div>
          {Object.entries(test.columns).map(([table, columns]) => (
            <div key={table} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <div className="mb-2 text-xs font-semibold text-white">{byName[table]?.label || table}</div>
              <MappingEditor table={byName[table]} columns={columns} value={mapping[table]}
                             onChange={(next) => setMapping({ ...mapping, [table]: next })} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
