/**
 * Which school an address belongs to - plain, so both the browser
 * (lib/school.js) and the server's proxy (proxy.js) read it the same way.
 */

// The address without a school in front: "localhost" here, the real
// domain (e.g. "vocira.com") when deployed.
export const ROOT_HOST = (process.env.NEXT_PUBLIC_ROOT_HOST || "localhost").toLowerCase();

// Vocira's own addresses - never a school (services/tenants.py)
const NOT_A_SCHOOL = new Set(["www", "app", "admin", "superadmin", "api"]);

/** The school subdomain of a host name ("medicaps.localhost" -> "medicaps"), or "". */
export function subdomainOf(hostname) {
  const host = (hostname || "").toLowerCase();
  if (!host.endsWith(`.${ROOT_HOST}`)) return "";
  const label = host.slice(0, -(ROOT_HOST.length + 1));
  return label && !label.includes(".") && !NOT_A_SCHOOL.has(label) ? label : "";
}
