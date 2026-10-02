"use client";

/*
 * Integrations - every school's records system at a glance, for the
 * platform's super admin: which provider, whether it works, the last sync,
 * how many records Vocira has, and the last problem. Manage opens the same
 * panel the school's admin has, for any school.
 */

import { useState } from "react";
import { RefreshCw, Settings2 } from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Modal from "@/app/admin/_components/ui/Modal";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { adminFetch, formatTime, useAdminData } from "@/app/admin/useAdminApi";
import IntegrationPanel from "@/app/admin/_components/records/IntegrationPanel";
import {
  HUB, MODE_TEXT, RUN_LABEL, STATE_TEXT_CLASS, STATUS_BADGE, schoolPath, syncState,
} from "@/app/admin/_components/records/shared";
import FullScreenLoader from "@/components/FullScreenLoader";

const EMPTY = { schools: [] };

function health(school) {
  if (!school.provider) return { label: "general questions only", variant: "neutral" };
  if (school.running) return { label: "syncing…", variant: "neutral" };
  if (school.provider.mode === "unavailable") return { label: "official integration required", variant: "warning" };
  if (school.status === "error") return { label: "not working", variant: "danger" };
  if (school.status === "attention") return { label: "needs attention", variant: "warning" };
  if (school.connected) return { label: "connected", variant: "success" };
  return { label: "not connected yet", variant: "warning" };
}

export default function IntegrationsPage() {
  const { data, loading, error, reload } = useAdminData(`${HUB}/overview`, EMPTY, { pollMs: 15000 });
  const [managing, setManaging] = useState(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  async function syncNow(school) {
    setBusy(school.school);
    try {
      await adminFetch(`${schoolPath(school.school)}/sync`, { method: "POST", body: JSON.stringify({ trigger: "manual" }) });
      setNotice(`Sync started for ${school.name}.`);
      setTimeout(() => reload({ silent: true }), 2500);
    } catch (err) {
      setNotice(err.message || "Could not start a sync.");
    } finally {
      setBusy("");
    }
  }

  if (loading && !data.schools.length) return <FullScreenLoader label="Loading integrations…" />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Integrations</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Where each school&apos;s student records come from. Every school&apos;s records are kept apart.
          </p>
        </div>
        <Button variant="outline" onClick={() => reload()}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>
      {error && <p className="text-xs text-rose-300">{error}</p>}
      {notice && <p className="text-xs text-emerald-200">{notice}</p>}

      <Card>
        <CardHeader title="Schools" description="Provider, status, last sync, records in Vocira and the last problem." />
        <Table>
          <THead>
            <TR>
              <TH>School</TH>
              <TH>Records provider</TH>
              <TH>Status</TH>
              <TH>Last sync</TH>
              <TH>Records</TH>
              <TH>Last problem</TH>
              <TH></TH>
            </TR>
          </THead>
          <TBody>
            {data.schools.map((school) => {
              const h = health(school);
              const badge = school.provider && STATUS_BADGE[school.provider.status];
              const counts = Object.entries(school.counts || {}).filter(([, n]) => n);
              return (
                <TR key={school.school}>
                  <TD>
                    <div className="font-medium text-white">{school.name}</div>
                    <div className="font-mono text-[10px] text-text-secondary/70">{school.subdomain}</div>
                  </TD>
                  <TD>
                    <div className="text-white">{school.provider ? school.provider.label : "—"}</div>
                    <div className="text-[10px] text-text-secondary/70">
                      {school.provider ? MODE_TEXT[school.provider.mode] : "no records system"}
                    </div>
                    {badge && <Badge className="mt-1" label={badge.label} variant={badge.variant} />}
                  </TD>
                  <TD><Badge label={h.label} variant={h.variant} /></TD>
                  <TD className="whitespace-nowrap text-[11px]">
                    {school.last_sync ? (
                      <>
                        <div>{formatTime(school.last_sync.at)}</div>
                        <div className={STATE_TEXT_CLASS[syncState(school.last_sync)]}>
                          {RUN_LABEL[syncState(school.last_sync)]}
                        </div>
                      </>
                    ) : "never"}
                  </TD>
                  <TD className="max-w-[220px] text-[11px]">
                    {counts.length ? counts.map(([t, n]) => `${t} ${Number(n).toLocaleString()}`).join(" · ") : "—"}
                  </TD>
                  <TD className="max-w-[260px] text-[11px] text-rose-200/90">
                    {school.last_error ? `${formatTime(school.last_error.started_at)}: ${school.last_error.error}` : "—"}
                  </TD>
                  <TD className="whitespace-nowrap text-right">
                    {school.provider && school.provider.mode !== "native" && school.provider.setup !== "upload" && school.connected && (
                      <Button variant="outline" onClick={() => syncNow(school)} disabled={busy === school.school || school.running}
                              title="Sync now">
                        <RefreshCw className={`h-3.5 w-3.5 ${school.running ? "animate-spin" : ""}`} />
                      </Button>
                    )}{" "}
                    <Button variant="outline" onClick={() => setManaging(school)}>
                      <Settings2 className="h-3.5 w-3.5" /> Manage
                    </Button>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </Card>

      {managing && (
        <Modal id="manage-integration" size="xl" title={`${managing.name} - records integration`}
               description="Connect, change, test, sync or disconnect this school's records system."
               onClose={() => { setManaging(null); reload({ silent: true }); }}>
          <IntegrationPanel schoolId={managing.school} superAdmin onChanged={() => reload({ silent: true })} />
        </Modal>
      )}
    </div>
  );
}
