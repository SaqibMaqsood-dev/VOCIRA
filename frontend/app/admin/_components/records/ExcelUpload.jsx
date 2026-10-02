"use client";

/*
 * An Excel / CSV file into one of Vocira's tables, in three steps:
 * choose the table and the file; check how its columns map (Vocira suggests
 * what it recognises) and the first rows; import. Importing replaces the
 * school's copy of that table with the file's rows.
 */

import { useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";

import { adminFetch } from "@/app/admin/useAdminApi";

import MappingEditor from "./MappingEditor";
import { BUTTON, LABEL, SELECT } from "./shared";

export default function ExcelUpload({ path, tables, initialTable, onImported }) {
  const [table, setTable] = useState(initialTable || tables[0]?.table || "students");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");

  const spec = tables.find((t) => t.table === table);

  async function send(chosenFile, dryRun, chosenMapping) {
    const form = new FormData();
    form.append("file", chosenFile);
    form.append("dry_run", dryRun ? "true" : "false");
    form.append("mapping", chosenMapping ? JSON.stringify(chosenMapping) : "");
    return adminFetch(`${path}/upload/${table}`, { method: "POST", body: form });
  }

  async function check(chosenFile, chosenMapping) {
    setBusy("check");
    setProblem("");
    try {
      const res = await send(chosenFile, true, chosenMapping);
      setPreview(res);
      if (!chosenMapping) {
        setMapping(Object.fromEntries(Object.entries(res.mapping || res.suggested || {}).filter(([, v]) => v)));
      }
    } catch (err) {
      setProblem(err.message || "The file could not be read.");
      setPreview(null);
    } finally {
      setBusy("");
    }
  }

  async function importIt() {
    setBusy("import");
    setProblem("");
    try {
      const res = await send(file, false, mapping);
      setFile(null);
      setPreview(null);
      onImported?.(`${spec?.label || table}: ${res.rows} rows imported${res.skipped ? `, ${res.skipped} left out` : ""}.`);
    } catch (err) {
      setProblem(err.message || "Could not import the file.");
    } finally {
      setBusy("");
    }
  }

  const columnsShown = spec ? spec.fields.map((f) => f.name) : [];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
        <label className="block">
          <span className={LABEL}>Table</span>
          <select className={SELECT} value={table}
                  onChange={(e) => { setTable(e.target.value); setPreview(null); setFile(null); }}>
            {tables.map((t) => (
              <option key={t.table} value={t.table}>{t.label}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className={LABEL}>File (.xlsx or .csv, up to 5 MB)</span>
          <label className={`${BUTTON} cursor-pointer`}>
            <FileSpreadsheet className="h-3.5 w-3.5" />
            {file ? file.name : "Choose a file"}
            <input type="file" accept=".xlsx,.csv" className="hidden"
                   onChange={(e) => {
                     const chosen = e.target.files?.[0];
                     e.target.value = "";
                     if (chosen) {
                       setFile(chosen);
                       check(chosen, null);
                     }
                   }} />
          </label>
        </label>
      </div>

      {busy === "check" && <p className="text-xs text-text-secondary">Reading the file…</p>}
      {problem && <p className="text-xs text-rose-300">{problem}</p>}

      {preview && (
        <div className="space-y-4">
          <div className="text-xs text-text-secondary">
            {preview.rows_in_file} row(s) in the file · columns: {preview.columns.join(", ")}
          </div>
          <MappingEditor table={spec} columns={preview.columns} value={mapping} onChange={setMapping} />
          <div className="flex flex-wrap gap-2">
            <button type="button" className={BUTTON} onClick={() => check(file, mapping)} disabled={!!busy}>
              Check with this mapping
            </button>
            <button type="button" className={`${BUTTON} border-accent-primary/50 bg-accent-primary/80 hover:bg-accent-primary`}
                    onClick={importIt} disabled={!!busy || !preview.ok}>
              <Upload className="h-3.5 w-3.5" />
              {busy === "import" ? "Importing…" : preview.ok ? `Import ${preview.rows} rows` : "Fix the mapping first"}
            </button>
          </div>
          {!preview.ok && <p className="text-xs text-rose-300">{preview.error}</p>}
          {(preview.warnings || []).map((w) => (
            <p key={w} className="text-[11px] text-amber-200">{w}</p>
          ))}
          {preview.ok && preview.preview?.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="min-w-full text-left text-[11px] text-text-secondary">
                <thead className="bg-white/[0.04] text-[10px] uppercase tracking-wider">
                  <tr>{columnsShown.map((c) => <th key={c} className="px-2 py-1.5">{c}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {preview.preview.map((row, i) => (
                    <tr key={i}>
                      {columnsShown.map((c) => <td key={c} className="px-2 py-1.5 text-white/90">{row[c] ?? ""}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
