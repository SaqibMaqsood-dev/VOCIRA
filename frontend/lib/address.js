/**
 * Which school an address belongs to - plain, so both the browser
 * (lib/school.js) and the server's proxy (proxy.js) read it the same way.
 *
 * A school's address is written one of two ways:
 *
 *   subdomain  medicaps.vocira.com (here medicaps.localhost:3000) - needs a
 *              domain of our own with a wildcard (*.vocira.com).
 *   path       vocira.vercel.app/s/medicaps - for an address that cannot
 *              have subdomains, such as a *.vercel.app one. Opening that link
 *              remembers the school in this browser (a cookie), and every
 *              page after it - /assistant, /login, /admin - is that school's.
 *
 * NEXT_PUBLIC_SCHOOL_ADDRESSES picks one; left unset, a *.vercel.app root is
 * "path" and anything else "subdomain".
 */

// The address without a school in front: "localhost" here, the real
// domain (e.g. "vocira.com" or "vocira.vercel.app") when deployed.
export const ROOT_HOST = (process.env.NEXT_PUBLIC_ROOT_HOST || "localhost").toLowerCase();

export const SCHOOL_ADDRESSES = (
  process.env.NEXT_PUBLIC_SCHOOL_ADDRESSES || (ROOT_HOST.endsWith(".vercel.app") ? "path" : "subdomain")
).toLowerCase();

export const PATH_MODE = SCHOOL_ADDRESSES === "path";

// path mode: the school this browser is in
export const SCHOOL_COOKIE = "vocira_school";

// path mode: /s/vocira leaves the school for Vocira's own site ("vocira" is a
// reserved name - never a school's, services/tenants.py RESERVED_SUBDOMAINS)
export const LEAVE_SCHOOL = "vocira";

// Vocira's own addresses - never a school (services/tenants.py)
const NOT_A_SCHOOL = new Set(["www", "app", "admin", "superadmin", "api", LEAVE_SCHOOL]);

const LABEL = /^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$/;

function asSchool(label) {
  const value = (label || "").trim().toLowerCase();
  return LABEL.test(value) && !NOT_A_SCHOOL.has(value) ? value : "";
}

/** The school subdomain of a host name ("medicaps.localhost" -> "medicaps"), or "". */
export function subdomainOf(hostname) {
  const host = (hostname || "").toLowerCase();
  if (!host.endsWith(`.${ROOT_HOST}`)) return "";
  const label = host.slice(0, -(ROOT_HOST.length + 1));
  return label.includes(".") ? "" : asSchool(label);
}

/** path mode: the school remembered in a Cookie header / document.cookie, or "". */
export function schoolFromCookies(cookies) {
  const found = String(cookies || "")
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${SCHOOL_COOKIE}=`));
  if (!found) return "";
  try {
    return asSchool(decodeURIComponent(found.slice(SCHOOL_COOKIE.length + 1)));
  } catch {
    return "";
  }
}
