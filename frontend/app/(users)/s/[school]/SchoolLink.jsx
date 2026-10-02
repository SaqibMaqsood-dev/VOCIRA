"use client";

import { useEffect, useState } from "react";

import FullScreenLoader from "@/components/FullScreenLoader";
import { LEAVE_SCHOOL, PATH_MODE } from "@/lib/address";
import { clearSession, getAccessToken } from "@/lib/session";
import { fetchSchoolAt, forgetSchool, rememberSchool, safeNext, schoolUrl, subdomainOfPage } from "@/lib/school";

/**
 * /s/<school> - a school's link.
 *
 * With subdomain addresses it is the older kind of link: it sends the guest
 * on to the school's own address (medicaps.vocira.com).
 *
 * With path addresses (vocira.vercel.app - lib/address.js) it IS the
 * school's address: this browser is put into the school and sent on to
 * ?next= (the school's home by default). A sign-in belongs to the address it was
 * made on, so one from another school - or the super admin's - is signed out
 * first. /s/vocira leaves the school for Vocira's own site.
 *
 * An unknown school says so - it never shows which schools there are.
 */
export default function SchoolLink({ schoolId }) {
  const [state, setState] = useState("looking");

  useEffect(() => {
    let cancelled = false;
    const wanted = schoolId.trim().toLowerCase();
    const next = new URLSearchParams(window.location.search).get("next");

    if (PATH_MODE && wanted === LEAVE_SCHOOL) {
      if (subdomainOfPage() && getAccessToken()) clearSession();
      forgetSchool();
      window.location.replace(safeNext(next, "/"));
      return undefined;
    }

    fetchSchoolAt(wanted)
      .then((school) => {
        if (cancelled) return;
        if (!school) {
          setState("unknown");
        } else if (PATH_MODE) {
          if (subdomainOfPage() !== school.subdomain && getAccessToken()) clearSession();
          rememberSchool(school.subdomain);
          window.location.replace(safeNext(next, "/"));
        } else {
          window.location.replace(schoolUrl(school.subdomain));
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
