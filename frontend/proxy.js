import { NextResponse } from "next/server";

import { LEAVE_SCHOOL, SCHOOL_COOKIE, schoolFromCookies, subdomainOf, usesPathAddresses } from "./lib/address";

/**
 * The super admin's sign-in lives on Vocira's main address only.
 *
 * Subdomain addresses (localhost:3000/super_admin_login): on a school's
 * address (medicaps.localhost:3000/super_admin_login) there is no such page -
 * the server answers "not found" before any of it reaches the browser.
 *
 * Path addresses (vocira.vercel.app - lib/address.js): there is one address,
 * and a browser inside a school is first taken out of it (/s/vocira signs
 * out that school's account and forgets the school), then shown the sign-in.
 *
 * The auth service refuses the super admin at a school's address anyway.
 */
export function proxy(request) {
  // the address the page was asked for decides which kind of addresses it has
  const hostname = (request.headers.get("host") || "").split(":")[0];
  if (usesPathAddresses(hostname)) {
    if (schoolFromCookies(request.headers.get("cookie") || "") || request.cookies.get(SCHOOL_COOKIE)?.value) {
      const out = new URL(`/s/${LEAVE_SCHOOL}`, request.url);
      out.searchParams.set("next", "/super_admin_login");
      return NextResponse.redirect(out);
    }
    return NextResponse.next();
  }
  if (subdomainOf(hostname)) {
    // a private folder name (_...) is never a route, so this is the 404 page
    return NextResponse.rewrite(new URL("/_no-such-page", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/super_admin_login",
};
