"use client";

import { useEffect, useState } from "react";

import { getAccessToken } from "@/lib/session";
import { fetchSchoolAt, subdomainOfPage } from "@/lib/school";

/**
 * Which site this page is: Vocira's own (the plain address,
 * localhost:3000 / vocira.com - what Vocira is, for schools) or a
 * school's (medicaps.localhost:3000 - that school's assistant).
 *
 * null until read in the browser: the server does not know the address
 * the page was opened on, and guessing would flash the wrong menu.
 *
 *   { subdomain, isSchool, loggedIn, product }
 *   product = Vocira's own site: the plain address, signed in or not.
 *   Only the platform's super admin signs in there (a school's people
 *   sign in at their school's address, and a sign-in belongs to the
 *   address it was made on) - so it never turns into a school's app.
 */
export function useSite() {
  const [site, setSite] = useState(null);

  useEffect(() => {
    const read = () => {
      const subdomain = subdomainOfPage();
      const loggedIn = Boolean(getAccessToken());
      setSite({ subdomain, isSchool: Boolean(subdomain), loggedIn, product: !subdomain });
    };
    read();
    window.addEventListener("auth-change", read);
    return () => window.removeEventListener("auth-change", read);
  }, []);

  return site;
}

/**
 * The school whose address this page is on.
 * undefined while looking, null when the address is no school's.
 */
export function useSchoolOfPage(subdomain) {
  const [school, setSchool] = useState(undefined);

  useEffect(() => {
    if (!subdomain) return;
    let cancelled = false;
    fetchSchoolAt(subdomain)
      .then((found) => !cancelled && setSchool(found))
      .catch(() => !cancelled && setSchool(undefined));
    return () => {
      cancelled = true;
    };
  }, [subdomain]);

  return subdomain ? school : null;
}
