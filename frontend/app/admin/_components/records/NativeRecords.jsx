"use client";

/*
 * The school's records as Vocira keeps them, table by table.
 *
 * On Vocira Native Records they are edited here: added and changed one at a
 * time, a whole table imported from an Excel/CSV file, and attendance
 * marked class by class on the register. On a copied source (Excel/CSV,
 * Google Sheets, REST API, database) the same tables are shown read-only,
 * so the admin can see what Vocira has.
 */

import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, FileSpreadsheet, Pencil, Plus, Search, Trash2 } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card } from "@/app/admin/_components/ui/Card";
import Modal from "@/app/admin/_components/ui/Modal";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { adminFetch } from "@/app/admin/useAdminApi";

import ExcelUpload from "./ExcelUpload";
import { BUTTON, INPUT, LABEL, RECORDS, SELECT, keepEnter } from "./shared";

const PAGE = 25;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MARK_STYLE = {
  Present: "border-emerald-400/40 bg-emerald-400/15 text-emerald-100",
  Absent: "border-rose-400/40 bg-rose-400/15 text-rose-100",
  Leave: "border-amber-400/40 bg-amber-400/15 text-amber-100",
  Late: "border-sky-400/40 bg-sky-400/15 text-sky-100",
};

function FieldInput({ field, value, onChange, statuses }) {
  const common = { className: INPUT, value: value ?? "", onChange: (e) => onChange(e.target.value) };
  if (field.type === "longtext") return <textarea rows={4} {...common} />;
  if (field.type === "status") {
    return (
      <select {...common} className={SELECT}>
        <option value="">—</option>
        {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
    );
  }
  if (field.type === "day") {
    return (
      <select {...common} className={SELECT}>
        <option value="">—</option>
        {DAYS.map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
    );
  }
  const type = { number: "number", date: "date", email: "email", tel: "tel", time: "time" }[field.type] || "text";
  return <input type={type} step={type === "number" ? "any" : undefined} {...common} />;
}

function Register({ statuses, onSaved }) {
  const [klass, setKlass] = useState("");
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const [marks, setMarks] = useState({});
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const load = useCallback(async (k, d) => {
    try {
      const res = await adminFetch(`${RECORDS}/attendance/register?class=${encodeURIComponent(k)}&date=${d}`);
      setData(res);
      setKlass(res.class);
      setMarks(Object.fromEntries(res.students.map((s) => [s.student_id, s.status || "Present"])));
    } catch (err) {
      setProblem(err.message || "Could not load the register.");
    }
  }, []);

  useEffect(() => { load("", day); }, [load]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save() {
    setBusy(true);
    setProblem("");
    try {
      const res = await adminFetch(`${RECORDS}/attendance/register`, { method: "POST", body: JSON.stringify({ date: day, marks }) });
      onSaved?.(`Attendance saved for ${res.marked} student(s) - ${klass}, ${day}.`);
      load(klass, day);
    } catch (err) {
      setProblem(err.message || "Could not save the register.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <p className="text-xs text-text-secondary">{problem || "Loading the register…"}</p>;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className={LABEL}>Class</span>
          <select className={SELECT} value={klass} onChange={(e) => load(e.target.value, day)}>
            {data.classes.length === 0 && <option value="">No classes yet</option>}
            {data.classes.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="block">
          <span className={LABEL}>Date</span>
          <input type="date" className={INPUT} value={day} onChange={(e) => { setDay(e.target.value); load(klass, e.target.value); }} />
        </label>
      </div>
      {data.students.length === 0 ? (
        <p className="text-xs text-text-secondary">No students in this class yet - add them on the Students tab (with their class).</p>
      ) : (
        <ul className="divide-y divide-white/5 rounded-xl border border-white/10">
          {data.students.map((s) => (
            <li key={s.student_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
              <span className="text-sm text-white">
                {s.roll_no ? <span className="mr-2 text-text-secondary">{s.roll_no}</span> : null}
                {s.student_name}
              </span>
              <span className="flex gap-1">
                {statuses.map((mark) => (
                  <button key={mark} type="button" onClick={() => setMarks({ ...marks, [s.student_id]: mark })}
                          className={`rounded-lg border px-2 py-1 text-[11px] font-semibold ${
                            marks[s.student_id] === mark ? MARK_STYLE[mark] : "border-white/10 text-text-secondary hover:bg-white/5"}`}>
                    {mark}
                  </button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      {problem && <p className="text-xs text-rose-300">{problem}</p>}
      {data.students.length > 0 && (
        <Button onClick={save} disabled={busy}>
          <ClipboardCheck className="h-3.5 w-3.5" />
          {busy ? "Saving…" : `Save attendance (${data.students.length})`}
        </Button>
      )}
    </div>
  );
}

export default function NativeRecords({ tables, statuses, editable, uploadPath, onChanged }) {
  const [tab, setTab] = useState(editable ? "register" : tables[0]?.table);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [list, setList] = useState({ rows: [], total: 0 });
  const [editing, setEditing] = useState(null); // {row?} - row null: a new record
  const [form, setForm] = useState({});
  const [importing, setImporting] = useState(false);
  const [problem, setProblem] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const spec = tables.find((t) => t.table === tab);
  const shownFields = spec ? spec.fields.slice(0, tab === "students" ? 5 : 6) : [];

  const load = useCallback(async () => {
    if (!spec) return;
    try {
      const res = await adminFetch(`${RECORDS}/${spec.table}?q=${encodeURIComponent(q)}&limit=${PAGE}&offset=${offset}`);
      setList(res);
      setProblem("");
    } catch (err) {
      setProblem(err.message || "Could not load the records.");
    }
  }, [spec, q, offset]);

  useEffect(() => { load(); }, [load]);

  const say = (text) => {
    setNotice(text);
    setTimeout(() => setNotice(""), 5000);
    onChanged?.();
  };

  function open(row) {
    setEditing({ row });
    setForm(row ? Object.fromEntries(spec.fields.map((f) => [f.name, row[f.name] ?? ""])) : {});
  }

  async function save() {
    setBusy(true);
    setProblem("");
    try {
      if (editing.row) {
        await adminFetch(`${RECORDS}/${spec.table}/${editing.row.id}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        await adminFetch(`${RECORDS}/${spec.table}`, { method: "POST", body: JSON.stringify(form) });
      }
      setEditing(null);
      say(`${spec.label}: saved.`);
      load();
    } catch (err) {
      setProblem(err.message || "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (!window.confirm("Delete this record?")) return;
    try {
      await adminFetch(`${RECORDS}/${spec.table}/${row.id}`, { method: "DELETE" });
      say(`${spec.label}: deleted.`);
      load();
    } catch (err) {
      setProblem(err.message || "Could not delete.");
    }
  }

  return (
    <Card>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {editable && (
          <button type="button" onClick={() => setTab("register")}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tab === "register" ? "bg-accent-primary/80 text-white" : "text-text-secondary hover:bg-white/5"}`}>
            Attendance register
          </button>
        )}
        {tables.map((t) => (
          <button key={t.table} type="button" onClick={() => { setTab(t.table); setQ(""); setOffset(0); }}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tab === t.table ? "bg-accent-primary/80 text-white" : "text-text-secondary hover:bg-white/5"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {notice && <p className="mb-3 text-xs text-emerald-200">{notice}</p>}

      {tab === "register" ? (
        <Register statuses={statuses} onSaved={say} />
      ) : spec ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="relative w-full max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-text-secondary" />
              <input className={`${INPUT} pl-8`} placeholder={`Search ${spec.label.toLowerCase()}…`} value={q}
                     onChange={(e) => { setQ(e.target.value); setOffset(0); }} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge label={`${list.total} record(s)`} />
              {editable && (
                <>
                  <button type="button" className={BUTTON} onClick={() => setImporting(true)}>
                    <FileSpreadsheet className="h-3.5 w-3.5" /> Import Excel / CSV
                  </button>
                  <Button onClick={() => open(null)}>
                    <Plus className="h-3.5 w-3.5" /> Add
                  </Button>
                </>
              )}
            </div>
          </div>
          {problem && <p className="text-xs text-rose-300">{problem}</p>}
          <Table>
            <THead>
              <TR>
                {shownFields.map((f) => <TH key={f.name}>{f.label}</TH>)}
                {tab === "students" && <TH>Parent</TH>}
                {editable && <TH></TH>}
              </TR>
            </THead>
            <TBody>
              {list.rows.length === 0 ? (
                <TR>
                  <TD colSpan={shownFields.length + 2} className="py-6 text-center text-text-secondary">
                    {q ? "Nothing matches." : editable ? `No ${spec.label.toLowerCase()} yet - add one, or import a file.` : "Nothing here yet."}
                  </TD>
                </TR>
              ) : (
                list.rows.map((row) => (
                  <TR key={row.id}>
                    {shownFields.map((f) => (
                      <TD key={f.name} className={f.type === "longtext" ? "max-w-[280px] truncate" : ""}>{row[f.name] ?? "—"}</TD>
                    ))}
                    {tab === "students" && <TD>{row.guardian_name || row.guardian_id || "—"}</TD>}
                    {editable && (
                      <TD className="whitespace-nowrap text-right">
                        <button type="button" className={BUTTON} onClick={() => open(row)} title="Edit"><Pencil className="h-3.5 w-3.5" /></button>{" "}
                        <button type="button" className={BUTTON} onClick={() => remove(row)} title="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                      </TD>
                    )}
                  </TR>
                ))
              )}
            </TBody>
          </Table>
          {list.total > PAGE && (
            <div className="flex items-center justify-end gap-2 text-xs text-text-secondary">
              <button type="button" className={BUTTON} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
              <span>{offset + 1}–{Math.min(offset + PAGE, list.total)} of {list.total}</span>
              <button type="button" className={BUTTON} disabled={offset + PAGE >= list.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
            </div>
          )}
        </div>
      ) : null}

      {editing && spec && (
        <Modal id="native-record" size="lg" title={`${editing.row ? "Edit" : "Add"} - ${spec.label}`}
               description={spec.fields.some((f) => f.native_optional) ? "An ID left empty is given automatically." : undefined}
               onClose={() => setEditing(null)}>
          <div className="grid gap-3 sm:grid-cols-2" onKeyDown={keepEnter}>
            {spec.fields.map((f) => (
              <label key={f.name} className={`block min-w-0 ${f.type === "longtext" ? "sm:col-span-2" : ""}`}>
                <span className={LABEL}>
                  {f.label}
                  {f.required && !f.native_optional ? <span className="text-rose-300"> *</span> : null}
                </span>
                <FieldInput field={f} value={form[f.name]} statuses={statuses}
                            onChange={(value) => setForm({ ...form, [f.name]: value })} />
              </label>
            ))}
          </div>
          {problem && <p className="mt-3 text-xs text-rose-300">{problem}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
          </div>
        </Modal>
      )}

      {importing && spec && (
        <Modal id="native-import" size="xl" title={`Import ${spec.label} from Excel / CSV`}
               description="The file's rows replace this table's records." onClose={() => setImporting(false)}>
          <ExcelUpload path={uploadPath} tables={tables} initialTable={spec.table}
                       onImported={(text) => { setImporting(false); say(text); load(); }} />
        </Modal>
      )}
    </Card>
  );
}
