"use client";

/*
 * Schools - one voice agent, many schools.
 *
 * Each school brings its own knowledge base (a Pinecone namespace of
 * its own documents) and its own records connector (ERPNext, or none
 * for a school that only answers general questions). The agent itself
 * is the same for all of them. This page only shows that setup; a
 * school is added in services/tenants.py and its documents on the
 * Knowledge page.
 */

import { useState } from "react";
import { Check, Copy, RefreshCw } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, formatTime } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";

const EMPTY = { schools: [], default: "educators" };

const SYNC_BADGE = {
  success: "success",
  running: "warning",
  failed: "danger",
};

export default function SchoolsPage() {
  const { data, loading, error, reload } = useAdminData("/livekit/admin/schools", EMPTY);
  const [copied, setCopied] = useState("");

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
        <Button variant="outline" onClick={reload}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {error && <p className="text-xs text-rose-300">{error}</p>}

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
            </TR>
          </THead>
          <TBody>
            {schools.map((school) => (
              <TR key={school.id}>
                <TD>
                  <div className="font-medium text-white">{school.name}</div>
                  <div className="text-[11px] text-text-secondary" dir="rtl">{school.name_ur}</div>
                  {school.id === data.default && (
                    <div className="mt-1 text-[10px] uppercase tracking-wider text-text-secondary">Default</div>
                  )}
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
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}
