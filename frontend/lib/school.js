"use client";

import {
  LEAVE_SCHOOL,
  SCHOOL_COOKIE,
  rootHostOf,
  schoolFromCookies,
  subdomainOf,
  usesPathAddresses,
} from "@/lib/address";
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

/**
 * Whether this page's address gives schools paths (vocira.vercel.app/s/medicaps)
 * rather than subdomains (medicaps.vocira.online) - lib/address.js.
 */
export function pathAddresses() {
  return usesPathAddresses(window.location.hostname);
}

/**
 * The school this page is for, or "" on Vocira's own site: the address's
 * subdomain - or, where addresses cannot have one (lib/address.js), the
 * school this browser was sent into by its /s/<school> link.
 */
export function subdomainOfPage() {
  if (pathAddresses()) return schoolFromCookies(document.cookie);
  return subdomainOf(window.location.hostname);
}

/** path mode: this browser is now in this school (the /s/<school> link). */
export function rememberSchool(subdomain) {
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${SCHOOL_COOKIE}=${encodeURIComponent(subdomain)}; path=/; max-age=31536000; samesite=lax${secure}`;
}

/** path mode: back on Vocira's own site. */
export function forgetSchool() {
  document.cookie = `${SCHOOL_COOKIE}=; path=/; max-age=0; samesite=lax`;
}


/** path mode: a page to go on to - only one of this site's own (never another site's). */
export function safeNext(value, fallback) {
  const next = (value || "").trim();
  return next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : fallback;
}

// The super admin's own sign-in, on the plain address only - a school's
// address answers it with "not found" (proxy.js). /login on the plain
// address is not a sign-in at all: Vocira's site has none for its visitors.
export const SUPER_ADMIN_LOGIN = "/super_admin_login";

/** Where this page signs in: a school's /login, or the super admin's own page. */
export function loginPath() {
  return subdomainOfPage() ? "/login" : SUPER_ADMIN_LOGIN;
}

/**
 * A school's own address, on the domain this page is on:
 * https://medicaps.vocira.online/assistant live, http://medicaps.localhost:3000/assistant
 * here - or in path mode https://vocira.vercel.app/s/medicaps (the school's
 * home), with ?next=/assistant for one of its pages.
 */
export function schoolUrl(subdomain, path = "/assistant") {
  const { protocol, port, host, hostname } = window.location;
  if (pathAddresses()) {
    const next = path && path !== "/" ? `?next=${encodeURIComponent(path)}` : "";
    return `${protocol}//${host}/s/${subdomain}${next}`;
  }
  return `${protocol}//${subdomain}.${rootHostOf(hostname)}${port ? `:${port}` : ""}${path}`;
}

/** Vocira's own site, without a school: https://vocira.online/ (path mode: leaving the school first). */
export function rootUrl(path = "/") {
  const { protocol, port, host, hostname } = window.location;
  if (pathAddresses()) {
    return `${protocol}//${host}/s/${LEAVE_SCHOOL}${path && path !== "/" ? `?next=${encodeURIComponent(path)}` : ""}`;
  }
  return `${protocol}//${rootHostOf(hostname)}${port ? `:${port}` : ""}${path}`;
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
