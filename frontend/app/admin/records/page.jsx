"use client";

/*
 * Records - the school's own records, for a school on Vocira Native Records.
 *
 * Which system a school's records come from is the platform super admin's
 * choice (Integrations page). When it is Native Records, the school's admin
 * keeps the records here: students, parents, classes, teachers, attendance,
 * fees, results, timetable and announcements. For any other system the
 * sidebar has no Records item, and this page only says where the records
 * come from. Parents never see any of this: they only talk to Vocira, which
 * reads only their own children's records.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { Card } from "@/app/admin/_components/ui/Card";
import { adminFetch } from "@/app/admin/useAdminApi";
import IntegrationPanel from "@/app/admin/_components/records/IntegrationPanel";
import NativeRecords from "@/app/admin/_components/records/NativeRecords";
import { HUB, schoolPath } from "@/app/admin/_components/records/shared";

export default function RecordsPage() {
  const [detail, setDetail] = useState(null);
  const [catalogue, setCatalogue] = useState(null);
  const [problem, setProblem] = useState("");
  const latest = useRef(0); // only the newest answer is shown
  const [changes, setChanges] = useState(0); // records edited below - the status card counts again

  const load = useCallback(async () => {
    const asked = ++latest.current;
    try {
      const next = await adminFetch(`${HUB}/mine`);
      if (asked === latest.current) setDetail(next);
    } catch (err) {
      setProblem(err.message || "Could not load the records.");
    }
  }, []);

  useEffect(() => {
    load();
    adminFetch(`${HUB}/catalogue`).then(setCatalogue).catch((err) => setProblem(err.message));
  }, [load]);

  const provider = detail?.status?.provider;
  const native = provider?.mode === "native";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Records</h1>
        <p className="mt-1 text-xs text-text-secondary">
          Where your students&apos; records come from. Vocira answers a parent only about their own children, and only
          what you allow it to read.
        </p>
      </div>
      {problem && <p className="text-xs text-rose-300">{problem}</p>}
      {detail && !native && (
        <Card>
          <p className="text-sm text-white">
            {provider
              ? `${detail.school.name}'s records come from ${provider.label}, set up by the Vocira team.`
              : `${detail.school.name} has no records system yet.`}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Records are kept here only when the school uses Vocira Native Records. Ask the Vocira team to change it.
          </p>
        </Card>
      )}
      {native && (
        <>
          <IntegrationPanel onChanged={load} refreshKey={changes} />
          {catalogue && (
            <div className="space-y-2">
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">Your records</h2>
              <NativeRecords
                tables={catalogue.tables}
                statuses={catalogue.attendance_statuses}
                editable
                uploadPath={schoolPath(detail.school.id)}
                onChanged={() => setChanges((n) => n + 1)}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
