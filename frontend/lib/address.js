/**
 * Which school an address belongs to - plain, so both the browser
 * (lib/school.js) and the server's proxy (proxy.js) read it the same way.
 *
 * It is all worked out from the address the page was opened on, so one
 * build is right everywhere - localhost:3000 here, vocira.online live, a
 * Vercel preview - with nothing to set per deployment. (It used to come
 * from NEXT_PUBLIC_ROOT_HOST alone, and a live build without it gave every
 * school a "medicaps.localhost" link.) A school's address is one of two kinds:
 *
 *   subdomain  medicaps.vocira.online (here medicaps.localhost:3000) - on
 *              a domain of our own, with a wildcard (*.vocira.online)
 *   path       vocira.vercel.app/s/medicaps - on an address that cannot
 *              have subdomains of ours (a *.vercel.app one, an IP address).
 *              Opening that link remembers the school in this browser (a
 *              cookie), and every page after it - /assistant, /login,
 *              /admin - is that school's.
 *
 * NEXT_PUBLIC_ROOT_HOST / NEXT_PUBLIC_SCHOOL_ADDRESSES ("path" or
 * "subdomain") can still pin them, for an address this cannot work out.
 */

const PINNED_ROOT = (process.env.NEXT_PUBLIC_ROOT_HOST || "").trim().toLowerCase();
const PINNED_ADDRESSES = (process.env.NEXT_PUBLIC_SCHOOL_ADDRESSES || "").trim().toLowerCase();

// Hosting addresses shared by many sites: a subdomain there is never ours,
// so schools get paths there.
const SHARED_HOSTS = [
  "vercel.app", "netlify.app", "pages.dev", "onrender.com", "herokuapp.com", "github.io",
  "web.app", "firebaseapp.com", "trycloudflare.com", "ngrok-free.app", "ngrok.app",
];

// Endings under which a domain of one's own has three parts (vocira.com.pk),
// not two (vocira.online).
const TWO_PART_ENDINGS = new Set([
  "com.pk", "net.pk", "org.pk", "edu.pk", "gov.pk", "gob.pk", "web.pk", "biz.pk", "fam.pk",
  "co.uk", "org.uk", "ac.uk", "gov.uk",
  "com.au", "net.au", "org.au", "edu.au",
  "co.in", "net.in", "org.in", "ac.in", "edu.in",
  "co.nz", "co.za", "co.ke", "com.sg", "com.my", "com.sa", "com.ae", "com.tr", "com.br", "com.bd", "com.ng",
]);

function cleanHost(hostname) {
  return (hostname || "").trim().toLowerCase().replace(/\.$/, "");
}

function isLocalhost(host) {
  return host === "localhost" || host.endsWith(".localhost");
}

function isIpAddress(host) {
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(host) || host.includes(":");
}

function isSharedHost(host) {
  return SHARED_HOSTS.some((shared) => host === shared || host.endsWith(`.${shared}`));
}

/**
 * The address without a school in front: "localhost" for
 * medicaps.localhost, "vocira.online" for medicaps.vocira.online. An
 * address whose schools are paths is its own (vocira.vercel.app).
 */
export function rootHostOf(hostname) {
  const host = cleanHost(hostname);
  if (PINNED_ROOT && (host === PINNED_ROOT || host.endsWith(`.${PINNED_ROOT}`))) return PINNED_ROOT;
  if (isLocalhost(host)) return "localhost";
  if (usesPathAddresses(host)) return host;
  const parts = host.split(".");
  const keep = TWO_PART_ENDINGS.has(parts.slice(-2).join(".")) ? 3 : 2;
  return parts.slice(-keep).join(".");
}

/** Whether schools at this address are paths (/s/medicaps) rather than subdomains. */
export function usesPathAddresses(hostname) {
  if (PINNED_ADDRESSES === "path") return true;
  if (PINNED_ADDRESSES === "subdomain") return false;
  const host = cleanHost(hostname);
  if (isLocalhost(host)) return false;
  // an IP address, a one-word intranet name or a shared hosting address
  // cannot be given a subdomain per school
  return !host.includes(".") || isIpAddress(host) || isSharedHost(host);
}

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

/** The school subdomain of a host name ("medicaps.vocira.online" -> "medicaps"), or "". */
export function subdomainOf(hostname) {
  const host = cleanHost(hostname);
  if (usesPathAddresses(host)) return "";
  const root = rootHostOf(host);
  if (!host.endsWith(`.${root}`)) return "";
  const label = host.slice(0, -(root.length + 1));
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
