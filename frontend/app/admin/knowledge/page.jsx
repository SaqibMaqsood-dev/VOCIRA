"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";

const EMPTY = { index: {}, last_sync: { state: "unknown" } };

export default function KnowledgePage() {
  const { data, loading, error, reload } = useAdminData(
    "/livekit/admin/knowledge",
    EMPTY
  );

  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState("");

  const index = data.index || {};
  const sync = data.last_sync || {};

  async function runSync() {
    try {
      setSyncing(true);
      setNotice("");
      const res = await adminFetch("/livekit/admin/knowledge/sync", {
        method: "POST",
      });
      setNotice(res.message || "Sync shuru ho gayi");
      setTimeout(reload, 3000);
    } catch (err) {
      setNotice(err.message || "Sync shuru nahi ho saki");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Knowledge base</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Vocira ke aam jawab isi vector index se bante hain.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button onClick={runSync} disabled={syncing}>
            {syncing ? "Starting…" : "Re-sync"}
          </Button>
        </div>
      </div>

      {(error || notice) && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
          {error || notice}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
          <CardHeader title="Dimensions" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : index.embedding_dimension ?? index.dimension ?? "—"}
          </p>
        </Card>
        <Card>
          <CardHeader title="Last sync" />
          <p className="text-sm font-medium text-white">
            {loading ? "…" : sync.state || "—"}
          </p>
        </Card>
      </div>

      {/* Pehle yahan "articles" ki hardcoded list thi (title, category,
          status) - aisa koi table backend mein hai hi nahi. Asli
          knowledge base Pinecone ka index hai, is liye ab us ki asli
          halat dikhayi jati hai. */}
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
              <TD colSpan={2} className="py-6 text-center text-xs text-text-secondary">
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
              <Row label="Vectors (all namespaces)" value={index.vectors_all_namespaces} />
              <Row label="Retrieval top_k" value={index.top_k} />
              <Row label="Last sync state" value={sync.state} />
              <Row label="Last sync at" value={sync.finished_at ? formatTime(sync.finished_at) : null} />
              <Row label="Last sync chunks" value={sync.chunks} />
              {index.error && <Row label="Error" value={index.error} />}
            </>
          )}
        </TBody>
      </Table>
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
