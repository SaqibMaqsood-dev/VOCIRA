"use client";

/*
 * Schools - one voice agent, many schools.
 *
 * Each school brings its own knowledge base (a Pinecone namespace of
 * its own documents) and its own records connector (ERPNext, or none
 * for a school that only answers general questions). The agent itself
 * is the same for all of them.
 *
 * A school is added here - no code change. The schools defined in code
 * (the first ones) are shown but cannot be changed or removed.
 */

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, FileText, Pencil, Plus, RefreshCw, Trash2, X } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";

const EMPTY = { schools: [], default: "educators" };

const SYNC_BADGE = {
  success: "success",
  running: "warning",
  failed: "danger",
};

const BLANK = { name: "", name_ur: "", helpline: "", records: "", records_env_prefix: "" };

const INPUT =
  "w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none transition focus:border-accent-primary/60";

export default function SchoolsPage() {
  const { data, loading, error, reload } = useAdminData("/livekit/admin/schools", EMPTY);
  const [copied, setCopied] = useState("");

  // The form: closed, adding a new school, or editing one (its id).
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [added, setAdded] = useState(null);

  const schools = data?.schools || [];

  async function copyLink(school) {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${school.guest_link}`);
      setCopied(school.id);
      setTimeout(() => setCopied(""), 2000);
    } catch {
      /* the link is on screen to copy by hand */
    }
  }

  function openAdd() {
    setEditing(null);
    setForm(BLANK);
    setProblem("");
    setAdded(null);
    setFormOpen(true);
  }

  function openEdit(school) {
    setEditing(school.id);
    setForm({
      name: school.name,
      name_ur: school.name_ur === school.name ? "" : school.name_ur,
      helpline: school.helpline,
      records: school.records || "",
      records_env_prefix: school.records_env_prefix || "",
    });
    setProblem("");
    setAdded(null);
    setFormOpen(true);
  }

  async function save(event) {
    event.preventDefault();
    setProblem("");
    setBusy("save");

    const body = JSON.stringify({
      name: form.name,
      name_ur: form.name_ur || null,
      helpline: form.helpline,
      records: form.records || null,
      records_env_prefix: form.records ? form.records_env_prefix || null : null,
    });

    try {
      if (editing) {
        await adminFetch(`/livekit/admin/schools/${encodeURIComponent(editing)}`, { method: "PATCH", body });
      } else {
        const result = await adminFetch("/livekit/admin/schools", { method: "POST", body });
        setAdded(result);
      }
      setFormOpen(false);
      setEditing(null);
      reload();
    } catch (err) {
      setProblem(err.message || "Could not save the school.");
    } finally {
      setBusy("");
    }
  }

  async function remove(school) {
    if (
      !window.confirm(
        `Remove ${school.name}?\n\nIts knowledge is cleared from the index and its guest link stops working. Its uploaded files stay on the server.`
      )
    ) {
      return;
    }
    setProblem("");
    setBusy(school.id);
    try {
      await adminFetch(`/livekit/admin/schools/${encodeURIComponent(school.id)}`, { method: "DELETE" });
      if (added?.id === school.id) setAdded(null);
      reload();
    } catch (err) {
      setProblem(err.message || "Could not remove the school.");
    } finally {
      setBusy("");
    }
  }

  if (loading) {
    return <FullScreenLoader label="Loading schools…" subLabel="Reading each school's setup" />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Schools</h1>
          <p className="mt-1 text-xs text-text-secondary">
            One Vocira agent serves every school below - each with its own knowledge base and records.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button onClick={openAdd} disabled={formOpen && !editing}>
            <Plus className="h-3.5 w-3.5" />
            Add school
          </Button>
        </div>
      </div>

      {(error || problem) && <p className="text-xs text-rose-300">{problem || error}</p>}

      {added && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="text-sm text-white">
              <p className="font-semibold">{added.name} is added.</p>
              <p className="mt-1 text-xs text-text-secondary">
                Next: add its documents, run a sync, then share its guest link. The agent needs no other change.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href={`/admin/knowledge?school=${encodeURIComponent(added.id)}`}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-white hover:bg-white/[0.12]"
              >
                <FileText className="h-3.5 w-3.5" />
                Add documents
              </Link>
              <button
                type="button"
                onClick={() => setAdded(null)}
                className="rounded-xl border border-white/10 px-2.5 py-2 text-text-secondary hover:text-white"
                title="Close"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </Card>
      )}

      {formOpen && (
        <Card>
          <CardHeader
            title={editing ? "Change school" : "Add a school"}
            description={
              editing
                ? "The school's id, knowledge base and guest link stay the same."
                : "The school gets its own knowledge base and guest link straight away. Its id comes from the English name."
            }
          />
          <form onSubmit={save} className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs text-text-secondary">
              <span>School name (English)</span>
              <input
                id="school-name"
                className={INPUT}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. City Grammar School"
                required
                minLength={3}
                maxLength={80}
              />
            </label>
            <label className="space-y-1 text-xs text-text-secondary">
              <span>Name in Urdu (optional, used in Urdu calls)</span>
              <input
                id="school-name-ur"
                className={INPUT}
                dir="rtl"
                value={form.name_ur}
                onChange={(e) => setForm({ ...form, name_ur: e.target.value })}
                placeholder="مثلاً سٹی گرامر اسکول"
                maxLength={80}
              />
            </label>
            <label className="space-y-1 text-xs text-text-secondary">
              <span>Helpline</span>
              <input
                id="school-helpline"
                className={INPUT}
                value={form.helpline}
                onChange={(e) => setForm({ ...form, helpline: e.target.value })}
                placeholder="e.g. 042-111-222-333"
                required
              />
            </label>
            <label className="space-y-1 text-xs text-text-secondary">
              <span>Student records</span>
              <select
                id="school-records"
                className={INPUT}
                style={{ colorScheme: "dark" }}
                value={form.records}
                onChange={(e) => setForm({ ...form, records: e.target.value })}
              >
                <option value="" style={{ backgroundColor: "#100944" }}>None - general questions only</option>
                <option value="erpnext" style={{ backgroundColor: "#100944" }}>ERPNext (credentials on the server)</option>
              </select>
            </label>
            {form.records && (
              <label className="space-y-1 text-xs text-text-secondary sm:col-span-2">
                <span>
                  Credentials prefix - the server reads PREFIX_BASE_URL, PREFIX_API_KEY and PREFIX_API_SECRET from its
                  environment. Keys are never typed here.
                </span>
                <input
                  id="school-prefix"
                  className={`${INPUT} font-mono uppercase`}
                  value={form.records_env_prefix}
                  onChange={(e) => setForm({ ...form, records_env_prefix: e.target.value.toUpperCase() })}
                  placeholder="e.g. CITYGRAMMAR_ERP"
                  required
                />
              </label>
            )}
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button type="submit" disabled={busy === "save"}>
                {busy === "save" ? "Saving…" : editing ? "Save changes" : "Add school"}
              </Button>
              <Button
                variant="outline"
                type="button"
                onClick={() => {
                  setFormOpen(false);
                  setEditing(null);
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Schools on this agent"
          description="Knowledge = the school's own documents in its own namespace. Records = the connector to its student records system."
        />
        <Table>
          <THead>
            <TR>
              <TH>School</TH>
              <TH>Helpline</TH>
              <TH>Knowledge</TH>
              <TH>Last sync</TH>
              <TH>Records</TH>
              <TH>Guest link</TH>
              <TH></TH>
            </TR>
          </THead>
          <TBody>
            {schools.map((school) => (
              <TR key={school.id}>
                <TD>
                  <div className="font-medium text-white">{school.name}</div>
                  <div className="text-[11px] text-text-secondary" dir="rtl">{school.name_ur}</div>
                  <div className="mt-1 text-[10px] uppercase tracking-wider text-text-secondary">
                    {school.id === data.default ? "Default · " : ""}
                    {school.built_in ? "Built in" : "Added here"}
                  </div>
                </TD>
                <TD className="whitespace-nowrap">{school.helpline}</TD>
                <TD>
                  <div className="text-white">
                    {school.vectors === null || school.vectors === undefined ? "—" : `${school.vectors} chunks`}
                  </div>
                  <div className="font-mono text-[11px] text-text-secondary">{school.namespace}</div>
                </TD>
                <TD>
                  <Badge
                    label={school.last_sync?.state || "never"}
                    variant={SYNC_BADGE[school.last_sync?.state] || "neutral"}
                  />
                  {school.last_sync?.finished_at && (
                    <div className="mt-1 text-[11px] text-text-secondary">
                      {formatTime(school.last_sync.finished_at)}
                    </div>
                  )}
                </TD>
                <TD>
                  {school.records ? (
                    <Badge label={`${school.records} connected`} variant="success" />
                  ) : (
                    <Badge label="General questions only" variant="neutral" />
                  )}
                </TD>
                <TD>
                  <button
                    type="button"
                    onClick={() => copyLink(school)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 font-mono text-[11px] text-text-secondary transition hover:border-white/20 hover:text-white"
                    title="Copy the guest link"
                  >
                    {copied === school.id ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {school.guest_link}
                  </button>
                </TD>
                <TD>
                  <div className="flex items-center gap-1.5">
                    <Link
                      href={`/admin/knowledge?school=${encodeURIComponent(school.id)}`}
                      className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:text-white"
                      title="Documents"
                    >
                      <FileText className="h-3.5 w-3.5" />
                    </Link>
                    {!school.built_in && (
                      <>
                        <button
                          type="button"
                          onClick={() => openEdit(school)}
                          className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:text-white"
                          title="Change"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => remove(school)}
                          disabled={busy === school.id}
                          className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:border-rose-400/40 hover:text-rose-200 disabled:opacity-50"
                          title="Remove"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}
