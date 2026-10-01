"use client";

import HomeHero from "@/components/HomeHero";
import VociraLanding from "@/components/VociraLanding";
import { rootUrl } from "@/lib/school";
import { useSchoolOfPage, useSite } from "@/lib/site";

/**
 * One home page, two sites:
 *   the plain address   -> what Vocira is (for schools and parents),
 *                          whether the super admin is signed in or not
 *   a school's address  -> that school's assistant, by name
 */
export default function HomeSwitch() {
  const site = useSite();
  const school = useSchoolOfPage(site?.subdomain);

  if (site === null) {
    // the address is read in the browser - nothing to guess before that
    return <div className="page-shell" />;
  }

  if (site.product) {
    return <VociraLanding />;
  }

  if (site.isSchool && school === null) {
    return (
      <div className="page-shell flex items-center justify-center">
        <div id="home-unknown-school" className="glass w-full max-w-md p-8 text-center">
          <h1 className="text-xl font-semibold text-text-primary">This is not a school&apos;s address</h1>
          <p className="mt-2 text-sm text-text-secondary">
            Please check the link, or ask your school for its assistant link.
          </p>
          <a
            href={rootUrl("/")}
            className="mt-6 inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card"
          >
            What is Vocira?
          </a>
        </div>
      </div>
    );
  }

  return <HomeHero schoolName={school?.name || ""} />;
}
