/*
 * Reading the API's timestamps.
 *
 * The database stores UTC in columns without a time zone, so the API
 * sends "2026-09-28T07:05:12" - no "Z", no offset. new Date() reads a
 * string like that as LOCAL time, which put every time on screen five
 * hours behind in Pakistan (a call at 12:05 showed as 07:05), and made a
 * fresh escalation look hours old.
 */

const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

export function parseServerTime(value) {
  if (value instanceof Date) return value;
  if (value === null || value === undefined || value === "") {
    return new Date(NaN);
  }

  const text = String(value).trim();

  // A bare calendar date is a day, not a moment - keep it local.
  if (DATE_ONLY.test(text)) return new Date(`${text}T00:00:00`);

  const iso = text.replace(" ", "T");
  return new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`);
}

// "2026-09-28" for the viewer's own calendar day - so a call at 1am
// Pakistan time is filed under that day, not the previous (UTC) one.
export function localDateKey(value) {
  const d = parseServerTime(value);
  if (Number.isNaN(d.getTime())) return "";

  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
