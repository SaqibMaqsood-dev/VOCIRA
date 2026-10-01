"use client";

/*
 * Schools - one voice agent, many schools.
 *
 * Each school brings its own knowledge base (a Pinecone namespace of
 * its own documents) and its own records connector: ERPNext, live
 * spreadsheet links (Google Sheets / CSV / Excel) kept in sync by the
 * server, or none for a school that only answers general questions.
 * The agent itself is the same for all.
 *
 * A school is added here - no code change. The schools defined in code
 * (the first ones) are managed the same way: edited, connected and
 * removed; a removed one keeps its knowledge and documents on the server.
 * The last school cannot be removed.
 */

import { useState } from "react";
import { Check, Copy, Pencil, Plus, QrCode, RefreshCw, Trash2, X } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";
import ConnectionWizard from "./ConnectionWizard";
import RecordsLinks from "./RecordsLinks";
import SchoolQr from "./SchoolQr";
import { schoolUrl } from "@/lib/school";

const EMPTY = { schools: [], default: "educators" };

const BLANK = { name: "", helpline: "", records: "", records_env_prefix: "", subdomain: "" };

// what an id or subdomain may look like (services/tenants.py)
const ADDRESS_CHARS = /[^a-z0-9-]/g;

const RECORDS_LABEL = { erpnext: "erpnext", spreadsheet: "live sheet", "open-school-mis": "open school mis" };

const INPUT =
  "w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none transition focus:border-accent-primary/60";

export default function SchoolsPage() {
  // refreshed quietly every minute, so a records link that starts failing shows up on its own
  const { data, loading, error, reload } = useAdminData("/livekit/admin/schools", EMPTY, { pollMs: 60000 });
  // the records systems a school can be connected to - each with the form it needs
  const { data: catalogue } = useAdminData("/livekit/admin/connectors", { connectors: [] });
  const kinds = catalogue?.connectors || [];
  const kindOf = (kind) => kinds.find((k) => k.kind === kind);
  const [copied, setCopied] = useState("");
  // the school whose QR code is open
  const [qrSchool, setQrSchool] = useState(null);

  // The form: closed, adding a new school, or editing one (its id).
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [added, setAdded] = useState(null);

  const schools = data?.schools || [];
  const editingSchool = editing ? schools.find((s) => s.id === editing) : null;
  const builtInEdit = !!editingSchool?.built_in;

  async function copyLink(school) {
    try {
      await navigator.clipboard.writeText(schoolUrl(school.subdomain));
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
      helpline: school.helpline,
      records: school.records || "",
      records_env_prefix: school.records_env_prefix || "",
      subdomain: school.subdomain_set || "",
    });
    setProblem("");
    setAdded(null);
    setFormOpen(true);
  }

  async function save(event) {
    event.preventDefault();
    setProblem("");
    setBusy("save");

    const chosen = kindOf(form.records);
    // A connected system (ERPNext, Open School MIS) is switched on by its own
    // "Save & connect" below, once its connection works - this form keeps
    // the school's records as they are until then.
    const records = chosen?.setup === "connection" ? editingSchool?.records ?? null : form.records || null;
    const body = JSON.stringify({
      name: form.name,
      helpline: form.helpline,
      records,
      records_env_prefix: records === "erpnext" ? form.records_env_prefix || null : null,
      // empty = the school's id is its address
      subdomain: form.subdomain.trim().toLowerCase() || null,
    });

    try {
      let savedId = editing;
      if (editing) {
        await adminFetch(`/livekit/admin/schools/${encodeURIComponent(editing)}`, { method: "PATCH", body });
      } else {
        const result = await adminFetch("/livekit/admin/schools", { method: "POST", body });
        setAdded(result);
        savedId = result.id;
      }
      if (["links", "connection"].includes(chosen?.setup)) {
        // Stay in the form: its links or its connection are set right below.
        setEditing(savedId);
      } else {
        setFormOpen(false);
        setEditing(null);
      }
      reload();
    } catch (err) {
      setProblem(err.message || "Could not save the school.");
    } finally {
      setBusy("");
    }
  }

  async function remove(school) {
    const what = school.built_in
      ? "Its guest link stops working and its records connection (with its keys) is deleted. Its knowledge and documents stay on the server."
      : "Its knowledge is cleared from the index, its records connection and files are deleted, and its guest link stops working. Its uploaded documents stay on the server.";
    const moves =
      school.id === data.default
        ? "\n\nIt is the default school - accounts without a school go to the next school from now on."
        : "";
    if (!window.confirm(`Remove ${school.name}?\n\n${what}${moves}`)) {
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

  // The full-screen loader only on the first load. After a save or an
  // upload the list refreshes behind the page - the loader used to
  // replace everything, so the open form and its upload messages were
  // thrown away and the page jumped back to the top.
  if (loading && schools.length === 0) {
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
                Next: the school&apos;s admin adds its documents on their Knowledge page and runs a sync, then its guest
                link is shared. The agent needs no other change.
              </p>
              {added.subdomain && (
                <p className="mt-2 font-mono text-xs text-accent-secondary">{schoolUrl(added.subdomain)}</p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
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
              builtInEdit
                ? "A school defined in code: its id, knowledge base and guest link stay as they are."
                : editing
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
              <span>Helpline</span>
              <input
                id="school-helpline"
                className={INPUT}
                value={form.helpline}
                onChange={(e) => setForm({ ...form, helpline: e.target.value })}
                placeholder="e.g. +92 300 1234567 or 042-111-222-333"
                required
              />
            </label>
            <label className="space-y-1 text-xs text-text-secondary sm:col-span-2">
              <span>Address (the school&apos;s own subdomain) - leave empty to use its id</span>
              <input
                id="school-subdomain"
                className={`${INPUT} font-mono lowercase`}
                value={form.subdomain}
                onChange={(e) => setForm({ ...form, subdomain: e.target.value.toLowerCase().replace(ADDRESS_CHARS, "") })}
                placeholder={editing ? editing : "e.g. citygrammar"}
                maxLength={40}
              />
              <span id="school-address-preview" className="block font-mono text-[11px] text-text-secondary/80">
                Guests open:{" "}
                {form.subdomain || editing
                  ? schoolUrl(form.subdomain || editing)
                  : "(the address comes from the English name)"}
              </span>
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
                {kinds.map((k) => (
                  <option key={k.kind} value={k.kind} style={{ backgroundColor: "#100944" }}>
                    {k.label}
                  </option>
                ))}
              </select>
            </label>
            {form.records === "erpnext" && editingSchool?.records_env_prefix && (
              <label className="space-y-1 text-xs text-text-secondary sm:col-span-2">
                <span>
                  Older setup: the server reads PREFIX_BASE_URL, PREFIX_API_KEY and PREFIX_API_SECRET from its
                  environment. Connecting below puts the keys in the panel (encrypted) instead.
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
            {kindOf(form.records)?.setup === "connection" &&
              (editing ? (
                <ConnectionWizard
                  key={form.records}
                  schoolId={editing}
                  spec={kindOf(form.records)}
                  onChange={() => reload({ silent: true })}
                />
              ) : (
                <p className="text-xs text-text-secondary sm:col-span-2">
                  Save first - then connect {kindOf(form.records).label} right here.
                </p>
              ))}
            {form.records === "spreadsheet" &&
              (editing && editingSchool?.records === "spreadsheet" ? (
                <RecordsLinks schoolId={editing} onChange={() => reload({ silent: true })} />
              ) : (
                <p className="text-xs text-text-secondary sm:col-span-2">
                  Save first - then paste each table&apos;s live link right here.
                </p>
              ))}
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
          description="Each school's documents are managed by its own admin. Records = the connector to its student records system."
        />
        <Table>
          <THead>
            <TR>
              <TH>School</TH>
              <TH>Helpline</TH>
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
                  <div className="mt-1 text-[10px] uppercase tracking-wider text-text-secondary">
                    {school.id === data.default ? "Default · " : ""}
                    {school.built_in ? "Built in" : "Added here"}
                  </div>
                </TD>
                <TD className="whitespace-nowrap">{school.helpline}</TD>
                <TD>
                  {school.records && school.records_ready === false ? (
                    <Badge
                      label={`${RECORDS_LABEL[school.records] || school.records} · ${
                        school.records === "spreadsheet" ? "no students link" : "not connected"
                      }`}
                      variant="warning"
                    />
                  ) : school.records && (school.records_sync_failing || school.connection_test_failed) ? (
                    <Badge
                      label={`${RECORDS_LABEL[school.records] || school.records} · ${
                        school.records_sync_failing ? "sync failing" : "last test failed"
                      }`}
                      variant="danger"
                    />
                  ) : school.records ? (
                    <Badge label={`${RECORDS_LABEL[school.records] || school.records} connected`} variant="success" />
                  ) : (
                    <Badge label="General questions only" variant="neutral" />
                  )}
                </TD>
                <TD>
                  <button
                    type="button"
                    onClick={() => copyLink(school)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 font-mono text-[11px] text-text-secondary transition hover:border-white/20 hover:text-white"
                    title="Copy the school's assistant link"
                  >
                    {copied === school.id ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {schoolUrl(school.subdomain, "").replace(/^https?:\/\//, "")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setQrSchool(school)}
                    className="ml-1.5 inline-flex items-center rounded-lg border border-white/10 bg-white/[0.04] p-1.5 text-text-secondary transition hover:border-white/20 hover:text-white"
                    title="QR code for the guest link"
                  >
                    <QrCode className="h-3.5 w-3.5" />
                  </button>
                </TD>
                <TD>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => openEdit(school)}
                      className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:text-white"
                      title="Edit"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(school)}
                      disabled={busy === school.id || schools.length <= 1}
                      className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:border-rose-400/40 hover:text-rose-200 disabled:opacity-50"
                      title={schools.length <= 1 ? "The last school cannot be removed" : "Remove"}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>

      {qrSchool && <SchoolQr school={qrSchool} link={schoolUrl(qrSchool.subdomain)} onClose={() => setQrSchool(null)} />}
    </div>
  );
}
