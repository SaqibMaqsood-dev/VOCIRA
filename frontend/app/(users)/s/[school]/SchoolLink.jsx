"use client";

import { useEffect, useState } from "react";

import FullScreenLoader from "@/components/FullScreenLoader";
import { fetchSchoolAt, schoolUrl } from "@/lib/school";

/**
 * /s/<school> - the older kind of school link (and the one a QR code can
 * carry when the school's own address cannot be used). It sends the
 * guest on to the school's own address. An unknown one says so - it
 * never shows which schools there are.
 */
export default function SchoolLink({ schoolId }) {
  const [state, setState] = useState("looking");

  useEffect(() => {
    let cancelled = false;

    fetchSchoolAt(schoolId.trim().toLowerCase())
      .then((school) => {
        if (cancelled) return;
        if (school) {
          window.location.replace(schoolUrl(school.subdomain));
        } else {
          setState("unknown");
        }
      })
      .catch(() => !cancelled && setState("unreachable"));

    return () => {
      cancelled = true;
    };
  }, [schoolId]);

  if (state === "looking") {
    return <FullScreenLoader label="Opening the assistant…" subLabel="Finding your school" />;
  }

  return (
    <div className="page-shell flex items-center justify-center">
      <div id="school-link-unknown" className="glass w-full max-w-md p-8 text-center">
        <h1 className="text-xl font-semibold text-text-primary">
          {state === "unknown" ? "This school link is not valid" : "The assistant cannot be reached"}
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          {state === "unknown"
            ? "Please ask your school for its assistant link - it is on the school's website, notices or QR code."
            : "Please try again in a moment."}
        </p>
      </div>
    </div>
  );
}
