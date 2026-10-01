import SchoolLink from "./SchoolLink";

/**
 * A school's own address for guests - /s/<school>, the link and QR code
 * on the super admin's Schools page. It remembers the school in this
 * browser and opens the Assistant.
 */
export default async function SchoolLinkPage({ params }) {
  const { school } = await params;
  return <SchoolLink schoolId={decodeURIComponent(school || "")} />;
}
