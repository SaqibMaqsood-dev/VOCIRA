"use client";

import { ROOT_HOST, subdomainOf } from "@/lib/address";
import { authFetch } from "@/lib/session";

/**
 * Which school a call goes to.
 *
 * A signed-in user's call always goes to their account's school - the
 * server reads it from the account, so nothing here can change it.
 *
 * A guest's school is the address they opened: every school has its
 * own subdomain - medicaps.vocira.com, and here medicaps.localhost:3000
 * (browsers send every *.localhost to this computer, no setup needed).
 * The page never lists the schools, so no school learns which others
 * use Vocira. On the plain address (no school in front) a guest is
 * asked to open their school's link instead.
 *
 * Each subdomain is its own origin, so logins and everything the
 * browser keeps are separate per school too.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000";

export { ROOT_HOST };

/** The school subdomain this page was opened on, or "" on the plain address. */
export function subdomainOfPage() {
  return subdomainOf(window.location.hostname);
}

// The super admin's own sign-in, on the plain address only - a school's
// address answers it with "not found" (proxy.js). /login on the plain
// address is not a sign-in at all: Vocira's site has none for its visitors.
export const SUPER_ADMIN_LOGIN = "/super_admin_login";

/** Where this page signs in: a school's /login, or the super admin's own page. */
export function loginPath() {
  return subdomainOfPage() ? "/login" : SUPER_ADMIN_LOGIN;
}

/** A school's own address: http://medicaps.localhost:3000/assistant */
export function schoolUrl(subdomain, path = "/assistant") {
  const { protocol, port } = window.location;
  return `${protocol}//${subdomain}.${ROOT_HOST}${port ? `:${port}` : ""}${path}`;
}

/** The plain address, without a school: http://localhost:3000/assistant */
export function rootUrl(path = "/") {
  const { protocol, port } = window.location;
  return `${protocol}//${ROOT_HOST}${port ? `:${port}` : ""}${path}`;
}

/**
 * The school at an address (a subdomain, or a school id from an older
 * /s/<id> link): { id, name, name_ur, subdomain }, or null if there is
 * none. Throws only when the server cannot be reached.
 */
export async function fetchSchoolAt(address) {
  const response = await fetch(`${API_URL}/livekit/tenant/${encodeURIComponent(address)}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Could not look up the school (${response.status}).`);
  }
  return response.json();
}

/** The school a signed-in user's calls go to - their account's. */
export async function fetchAccountSchool() {
  const response = await authFetch("/livekit/live_kit/school");
  if (!response.ok) {
    throw new Error(`Could not load your school (${response.status}).`);
  }
  return response.json();
}
