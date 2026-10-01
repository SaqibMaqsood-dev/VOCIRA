import { NextResponse } from "next/server";

import { subdomainOf } from "./lib/address";

/**
 * The super admin's sign-in lives on Vocira's main address only
 * (localhost:3000/super_admin_login). On a school's address
 * (medicaps.localhost:3000/super_admin_login) there is no such page:
 * the server answers "not found" before any of it reaches the browser.
 * The auth service refuses the super admin at a school's address anyway.
 */
export function proxy(request) {
  const hostname = (request.headers.get("host") || "").split(":")[0];
  if (subdomainOf(hostname)) {
    // a private folder name (_...) is never a route, so this is the 404 page
    return NextResponse.rewrite(new URL("/_no-such-page", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/super_admin_login",
};
