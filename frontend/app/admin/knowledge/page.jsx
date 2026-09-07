"use client";

/**
 * Knowledge base.
 *
 * Pehle yahan sirf "Re-sync" ka button tha - jo PEHLE SE rakhi hui
 * files parhta tha. Naya data daalne ke liye server tak pahunch
 * chahiye thi: file khud sahi folder mein rakho, phir sync dabao.
 *
 * Ab do raaste hain:
 *
 *   Upload   PDF ya TXT - bare documents ke liye
 *   Note     seedha likh dein - "timing badal gaya" ke liye PDF
 *            edit karna bewaqoofi hai
 *
 * Aur ek list: kaunsa document, kab aaya, kitne chunks bane. Ye
 * pehle kahin nazar nahi aata tha - index mein 32 vectors thay
 * magar ye pata nahi chalta tha ke wo kis kis cheez se bane.
 */

import { useEffect, useRef, useState } from "react";
import {
  FileText,
  FileType,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import {
  useAdminData,
  adminFetch,
  adminUpload,
  formatTime,
} from "@/app/admin/useAdminApi";

const EMPTY = { index: {}, last_sync: { state: "unknown" } };
const EMPTY_DOCS = { documents: [], total: 0, indexed: 0, chunks: 0 };

export default function KnowledgePage() {
  const { data, loading, error, reload } = useAdminData(
    "/livekit/admin/knowledge",
    EMPTY
  );

  const {
    data: docsData,
    loading: docsLoading,
    reload: reloadDocs,
  } = useAdminData("/livekit/admin/knowledge/documents", EMPTY_DOCS);

  const [syncing, setSyncing] = useState(false);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState("");

  const [noteOpen, setNoteOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");

  // Sync ka intezaar lamba ho sakta hai. Agar us dauran user kisi
  // aur page par chala jaye to component hat jata hai - aur us ke
  // baad setState karna React ka warning deta hai aur bekaar bhi
  // hai. Is liye har await ke baad ye dekh lete hain.
  const alive = useRef(true);
  const flashTimer = useRef(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimeout(flashTimer.current);
    };
  }, []);

  /**
   * Ek paighaam jo khud chala jata hai.
   *
   * Pehle notice hamesha ke liye chipka reh jata tha - "Sync started"
   * screen par para rehta chahe sync kab ki mukammal ho chuki ho.
   */
  const flash = (message, ms = 4000) => {
    setNotice(message);
    clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => {
      if (alive.current) setNotice("");
    }, ms);
  };

  const index = data.index || {};
  const sync = data.last_sync || {};
  const docs = docsData.documents || [];

  const pendingCount = docs.filter((d) => !d.indexed).length;

  const refreshAll = () => {
    reload();
    reloadDocs();
  };

  async function runSync() {
    setProblem("");
    setSyncing(true);
    setNotice("Syncing… this can take a moment.");

    try {
      await adminFetch("/livekit/admin/knowledge/sync", { method: "POST" });

      // Server 202 foran de deta hai - sync background mein chalti
      // hai. Pehle yahan ek setTimeout(4s) tha aur bas: notice hamesha
      // ke liye chipka reh jata tha, aur sync 4s se lambi hoti to
      // panel purane numbers dikhata rehta.
      //
      // Ab poochte rehte hain ke khatam hui ya nahi.
      const finished = await waitForSync();

      if (!alive.current) return;

      if (finished.state === "success") {
        refreshAll();
        flash("Sync complete — Vocira is using the latest documents.");
      } else if (finished.state === "failed") {
        setNotice("");
        // Ghalti poll se seedha lete hain, `data` se nahi - wo abhi
        // purani halat rakhta hai kyunke refresh hua hi nahi.
        setProblem(
          finished.error || "The sync failed. Check the server logs."
        );
      } else {
        // itni der ho gayi ke hum ne poochna chhor diya - sync shayad
        // ab bhi chal rahi ho, is liye ise nakami nahi kehte
        setNotice("");
        refreshAll();
      }
    } catch (err) {
      if (!alive.current) return;
      setNotice("");
      setProblem(err.message || "Could not start the sync.");
    } finally {
      if (alive.current) setSyncing(false);
    }
  }

  /**
   * State "running" se nikalne ka intezaar.
   *
   * Do minute (60 x 2s) tak poochte hain. Us se aage sync shayad ab
   * bhi chal rahi ho - is liye "timeout" ko nakami nahi kehte, bas
   * poochna chhor dete hain.
   */
  async function waitForSync() {
    for (let i = 0; i < 60; i++) {
      await sleep(2000);
      if (!alive.current) return { state: "gone" };

      try {
        const fresh = await adminFetch("/livekit/admin/knowledge");
        const last = fresh?.last_sync || {};
        if (last.state === "success" || last.state === "failed") {
          return last;
        }
      } catch {
        // ek poochne mein nakami se sab kuch nahi rukna chahiye -
        // agli baar phir koshish ho jayegi
      }
    }
    return { state: "timeout" };
  }

  async function onUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    try {
      setBusy("upload");
      setProblem("");
      const res = await adminUpload(
        "/livekit/admin/knowledge/documents",
        file
      );
      flash(`${res.name} uploaded. Run a sync to index it.`, 6000);
      reloadDocs();
    } catch (err) {
      setProblem(err.message || "Upload failed.");
    } finally {
      setBusy("");
    }
  }

  async function saveNote(event) {
    event.preventDefault();

    try {
      setBusy("note");
      setProblem("");
      const res = await adminFetch("/livekit/admin/knowledge/notes", {
        method: "POST",
        body: JSON.stringify({ title, text }),
      });
      flash(`${res.name} saved. Run a sync to index it.`, 6000);
      setTitle("");
      setText("");
      setNoteOpen(false);
      reloadDocs();
    } catch (err) {
      setProblem(err.message || "Could not save the note.");
    } finally {
      setBusy("");
    }
  }

  async function remove(name) {
    try {
      setBusy(name);
      setProblem("");
      await adminFetch(
        `/livekit/admin/knowledge/documents/${encodeURIComponent(name)}`,
        { method: "DELETE" }
      );
      flash(`${name} removed. Run a sync to update the index.`, 6000);
      reloadDocs();
    } catch (err) {
      setProblem(err.message || "Could not remove the document.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Knowledge base
          </h1>
          <p className="mt-1 text-xs text-text-secondary">
            Vocira answers general questions from these documents.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={refreshAll}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>

          <label
            className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-white/[0.12] ${
              busy === "upload" ? "pointer-events-none opacity-60" : ""
            }`}
          >
            <Upload className="h-3.5 w-3.5" />
            {busy === "upload" ? "Uploading…" : "Upload PDF / TXT"}
            <input
              type="file"
              accept=".pdf,.txt"
              onChange={onUpload}
              className="hidden"
            />
          </label>

          <Button variant="outline" onClick={() => setNoteOpen((o) => !o)}>
            <Plus className="h-3.5 w-3.5" />
            Add note
          </Button>

          <Button onClick={runSync} disabled={syncing}>
            {syncing ? "Syncing…" : "Re-sync"}
          </Button>
        </div>
      </div>

      {problem && (
        <div className="rounded-xl border border-red-400/30 bg-red-400/[0.07] px-3 py-2 text-xs text-red-200">
          {problem}
        </div>
      )}

      {(error || notice) && !problem && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
          {error || notice}
        </div>
      )}

      {pendingCount > 0 && (
        <div className="rounded-xl border border-accent-primary/30 bg-accent-primary/[0.08] px-3 py-2 text-xs text-white">
          {pendingCount} document{pendingCount === 1 ? "" : "s"} not indexed
          yet — press <span className="font-semibold">Re-sync</span> so Vocira
          can use {pendingCount === 1 ? "it" : "them"}.
        </div>
      )}

      {/* ---- note ka form ---- */}
      {noteOpen && (
        <Card>
          <CardHeader
            title="Add a note"
            description="For short things — a changed timing, a new rule, a holiday"
          />
          <form onSubmit={saveNote} className="mt-4 space-y-3">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title — e.g. School timings"
              maxLength={120}
              className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white placeholder:text-text-secondary/60 outline-none focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
            />
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              maxLength={20000}
              placeholder="School opens at 8 in the morning and closes at 2 in the afternoon…"
              className="w-full resize-none rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white placeholder:text-text-secondary/60 outline-none focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                type="button"
                onClick={() => setNoteOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={busy === "note"}>
                {busy === "note" ? "Saving…" : "Save note"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* ---- summary ---- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader title="Documents" />
          <p className="text-2xl font-semibold text-white">
            {docsLoading ? "…" : docsData.total}
          </p>
        </Card>
        <Card>
          <CardHeader title="Indexed chunks" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : index.vectors ?? "—"}
          </p>
        </Card>
        <Card>
          <CardHeader title="Embedding model" />
          <p className="truncate text-sm font-medium text-white">
            {loading ? "…" : index.embedding_model || "—"}
          </p>
        </Card>
        <Card>
          <CardHeader title="Last sync" />
          <p className="text-sm font-medium text-white">
            {loading ? "…" : sync.state || "—"}
          </p>
          {sync.finished_at && (
            <p className="mt-1 text-[11px] text-text-secondary">
              {formatTime(sync.finished_at)}
            </p>
          )}
        </Card>
      </div>

      {/* ---- documents ---- */}
      <Card>
        <CardHeader
          title="Documents"
          description="Vocira reads these — upload a file or add a note, then re-sync"
        />

        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH>Type</TH>
              <TH>Size</TH>
              <TH>Chunks</TH>
              <TH>Added</TH>
              <TH> </TH>
            </TR>
          </THead>
          <TBody>
            {docsLoading && (
              <TR>
                <TD
                  colSpan={6}
                  className="py-6 text-center text-xs text-text-secondary"
                >
                  Loading…
                </TD>
              </TR>
            )}

            {!docsLoading && docs.length === 0 && (
              <TR>
                <TD
                  colSpan={6}
                  className="py-6 text-center text-xs text-text-secondary"
                >
                  Nothing here yet. Upload a PDF or add a note.
                </TD>
              </TR>
            )}

            {docs.map((d) => (
              <TR key={d.name}>
                <TD className="text-xs text-white">
                  <span className="flex items-center gap-2">
                    {d.kind === "pdf" ? (
                      <FileType className="h-3.5 w-3.5 shrink-0 text-text-secondary" />
                    ) : (
                      <FileText className="h-3.5 w-3.5 shrink-0 text-text-secondary" />
                    )}
                    <span className="truncate">{d.name}</span>
                  </span>
                </TD>
                <TD className="whitespace-nowrap text-[11px] uppercase text-text-secondary">
                  {d.kind}
                </TD>
                <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                  {formatSize(d.size)}
                </TD>
                <TD className="whitespace-nowrap">
                  {d.indexed ? (
                    <span className="text-xs tabular-nums text-white">
                      {d.chunks}
                    </span>
                  ) : (
                    <Badge label="not indexed" variant="warning" />
                  )}
                </TD>
                <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                  {formatTime(d.modified)}
                </TD>
                <TD className="text-right">
                  <button
                    type="button"
                    onClick={() => remove(d.name)}
                    disabled={busy === d.name}
                    title="Remove"
                    className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 text-text-secondary transition-colors hover:border-red-400/40 hover:bg-red-400/10 hover:text-red-300 disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>

      {/* ---- index ki tafseel ---- */}
      <Card>
        <CardHeader title="Index" description="Pinecone vector store" />
        <Table>
          <THead>
            <TR>
              <TH>Property</TH>
              <TH>Value</TH>
            </TR>
          </THead>
          <TBody>
            {loading && (
              <TR>
                <TD
                  colSpan={2}
                  className="py-6 text-center text-xs text-text-secondary"
                >
                  Loading…
                </TD>
              </TR>
            )}

            {!loading && (
              <>
                <Row label="Index name" value={index.index} />
                <Row label="Namespace" value={index.namespace} />
                <Row
                  label="Dimension match"
                  value={
                    index.dimension_match === undefined ? null : (
                      <Badge
                        label={index.dimension_match ? "OK" : "MISMATCH"}
                        variant={index.dimension_match ? "success" : "warning"}
                      />
                    )
                  }
                />
                <Row label="Dimensions" value={index.embedding_dimension} />
                <Row label="Retrieval top_k" value={index.top_k} />
                <Row
                  label="Last sync at"
                  value={sync.finished_at ? formatTime(sync.finished_at) : null}
                />
                {index.error && <Row label="Error" value={index.error} />}
              </>
            )}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}

function Row({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <TR>
      <TD className="whitespace-nowrap text-[11px] text-text-secondary">
        {label}
      </TD>
      <TD className="text-xs text-white">{value}</TD>
    </TR>
  );
}

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

/** 7827 -> "7.6 KB" */
function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
