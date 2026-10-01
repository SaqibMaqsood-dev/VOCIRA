"use client";

/**
 * VOCIRA's own accounts - both admins and parents.
 *
 * VOCIRA accounts used to be invisible from everywhere. People
 * looked for them in ERPNext's Users and never found them - because
 * they live in Postgres, not in ERPNext. There was no way to create
 * an account and no way to change a password.
 *
 * parent_id is the most important field: it is what links to the
 * ERPNext Guardian record. Without it an account is still created
 * but reaches no child - so a missing one is shown clearly.
 */

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Eye,
  EyeOff,
  KeyRound,
  Link2Off,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Modal from "@/app/admin/_components/ui/Modal";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";

const EMPTY = { users: [], total: 0, linked: 0 };
const BASE = "/auth/admin/users";

// A new Guardian in ERPNext (added by hand, or by a bulk import) has
// no way to push a signal to this page, so it polls instead - every
// 20s is often enough to feel "automatic" without hammering the
// backend, and the poll is silent (see useAdminData) so it never
// interrupts whatever the admin is doing.
const POLL_MS = 20000;

const RECORDS_NAME = {
  erpnext: "ERPNext",
  "open-school-mis": "Open School MIS",
  spreadsheet: "the school's sheets",
};

export default function UsersPage() {
  const { data, loading, error, reload } = useAdminData(BASE, EMPTY, { pollMs: POLL_MS });

  // ERPNext's guardians - every one of them, not just the ones that
  // already have a Vocira login. The Parents table below is built
  // from this list so a guardian added in ERPNext shows up here on
  // its own, with a "Set password" action, instead of staying
  // invisible until someone remembers to add their account by hand.
  // the admin's own school - which records system its guardians come from
  const { data: mySchools } = useAdminData("/livekit/admin/schools", { schools: [] });
  const recordsKind = mySchools?.schools?.[0]?.records;
  const recordsName = RECORDS_NAME[recordsKind] || "the school's records";
  const { data: guardians } = useAdminData("/livekit/admin/guardians", [], {
    pollMs: POLL_MS,
  });

  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState("");

  const [form, setForm] = useState(null);   // { mode, user }
  const [picked, setPicked] = useState("");  // chuna hua Guardian ID

  // Email and name are filled in from the guardian, but the admin
  // can change them. While "typed" is null the guardian's value
  // applies; once something is typed, the admin's choice wins.
  const [emailTyped, setEmailTyped] = useState(null);
  const [nameTyped, setNameTyped] = useState(null);
  const [pwFor, setPwFor] = useState(null); // password reset ke liye

  // Filters which accounts show, by name or email - each table has
  // its own search now, since Administrators and Parents are
  // completely different lists (one person, hundreds of the other) -
  // one shared box meant a search meant for one table always ran
  // against the other too.
  const [adminSearch, setAdminSearch] = useState("");
  const [parentSearch, setParentSearch] = useState("");

  // Which of the two tables are expanded. Both start open - there
  // are only two sections here, not the dozens of guardians the
  // Queries page groups by, so hiding everything by default would
  // just be an extra click for no real benefit.
  const [openSections, setOpenSections] = useState(
    () => new Set(["admins", "parents"])
  );

  const toggleSection = (key) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const users = data.users || [];
  const guardianList = guardians || [];

  // Admins and parents are two entirely different things - one runs
  // the panel, the other asks about their child's data. Keeping both
  // in one list only confused both.
  const admins = users.filter((u) => u.role === "admin");
  const parents = users.filter((u) => u.role !== "admin");

  // Each row's ERPNext guardian record - so we can show whether the
  // login email matches it.
  const guardianById = Object.fromEntries(guardianList.map((g) => [g.id, g]));

  // The Parents table shows one row per ERPNext guardian - not one
  // row per Vocira account - so a guardian with no login yet still
  // appears, with a way to set one up right there - the only way to add
  // a login here, rather than picking them out of a dropdown of hundreds.
  //
  // An account whose parent_id points at nothing in ERPNext (deleted
  // guardian, typo, or simply no parent_id at all) has nowhere to
  // merge into, so it is kept as its own row - otherwise a login that
  // exists would just vanish from the list.
  const accountByGuardianId = new Map(
    parents.filter((u) => u.parent_id).map((u) => [u.parent_id, u])
  );
  const orphanAccounts = parents.filter(
    (u) => !u.parent_id || !guardianById[u.parent_id]
  );

  const parentRows = [
    ...guardianList.map((g) => {
      const account = accountByGuardianId.get(g.id) || null;
      return {
        key: g.id,
        user_id: account?.user_id,
        parent_id: g.id,
        name: account?.name || g.name,
        email: account?.email || g.email || "",
        role: account?.role || "guardian",
        created_at: account?.created_at || null,
        hasAccount: Boolean(account),
        guardianName: g.name,
      };
    }),
    ...orphanAccounts.map((u) => ({ ...u, key: u.user_id, hasAccount: true })),
  ];

  const adminNeedle = adminSearch.trim().toLowerCase();
  const parentNeedle = parentSearch.trim().toLowerCase();
  const matches = (u, needle) =>
    !needle ||
    (u.name || "").toLowerCase().includes(needle) ||
    (u.email || "").toLowerCase().includes(needle);

  const filteredAdmins = useMemo(
    () => admins.filter((u) => matches(u, adminNeedle)),
    [admins, adminNeedle]
  );
  const filteredParents = useMemo(
    () => parentRows.filter((u) => matches(u, parentNeedle)),
    [parentRows, parentNeedle]
  );

  const withoutLogin = parentRows.filter((r) => !r.hasAccount).length;
  const unlinked = orphanAccounts.filter((u) => u.role === "guardian");

  const chosen = guardianList.find((g) => g.id === picked) || null;

  function setupLogin(guardianId) {
    setForm(null);
    setPwFor(null);
    setPicked(guardianId);
    setEmailTyped(null);
    setNameTyped(null);
    setForm({ mode: "create", user: null });
  }

  const emailValue =
    emailTyped !== null ? emailTyped : chosen?.email || "";

  const nameValue =
    nameTyped !== null
      ? nameTyped
      : chosen?.name || form?.user?.name || "";

  function closeForm() {
    setForm(null);
    setProblem("");
  }

  function closePassword() {
    setPwFor(null);
    setProblem("");
  }

  const say = (message) => {
    setProblem("");
    setNotice(message);
    setTimeout(() => setNotice(""), 5000);
  };

  async function save(event) {
    event.preventDefault();
    const body = new FormData(event.target);
    const payload = Object.fromEntries(body.entries());

    try {
      setBusy("save");
      setProblem("");

      if (form.mode === "create") {
        const made = await adminFetch(BASE, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        say(`Account created for ${made.email}`);
      } else {
        await adminFetch(`${BASE}/${form.user.user_id}`, {
          method: "PATCH",
          body: JSON.stringify({
            email: payload.email,
            name: payload.name,
            parent_id: payload.parent_id,
            role: payload.role,
          }),
        });
        say(`${form.user.email} updated`);
      }

      setForm(null);
      reload();
    } catch (err) {
      setProblem(err.message || "Could not save.");
    } finally {
      setBusy("");
    }
  }

  async function resetPassword(event) {
    event.preventDefault();
    const password = new FormData(event.target).get("password");

    try {
      setBusy("pw");
      setProblem("");
      await adminFetch(`${BASE}/${pwFor.user_id}/password`, {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      say(`Password changed for ${pwFor.email}`);
      setPwFor(null);
    } catch (err) {
      setProblem(err.message || "Could not reset the password.");
    } finally {
      setBusy("");
    }
  }

  async function remove(user) {
    if (
      !window.confirm(
        `Delete ${user.email}? They will not be able to log in again.`
      )
    ) {
      return;
    }

    try {
      setBusy(user.user_id);
      setProblem("");
      await adminFetch(`${BASE}/${user.user_id}`, { method: "DELETE" });
      say(`${user.email} deleted`);
      reload();
    } catch (err) {
      setProblem(err.message || "Could not delete.");
    } finally {
      setBusy("");
    }
  }

  if (loading) {
    return (
      <FullScreenLoader
        label="Loading accounts…"
        subLabel="Fetching admin and parent logins"
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Accounts
          </h1>
          <p className="mt-1 text-xs text-text-secondary">
            Admin and parent logins for Vocira. These are separate from the
            logins of {recordsName}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* with a popup open, its problem shows inside it */}
      {problem && !form && !pwFor && <ProblemBox text={problem} />}

      {error && !problem && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
          {error}
        </div>
      )}

      {unlinked.length > 0 && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/[0.07] px-3 py-2.5 text-xs text-amber-100">
          <Link2Off className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {unlinked.length} parent
            {unlinked.length === 1 ? " is" : "s are"} not linked to a guardian
            record — Vocira cannot find their children until a Guardian ID is
            set.
          </span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader title={`Guardians (${recordsName})`} />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : guardianList.length}
          </p>
        </Card>
        <Card>
          <CardHeader title="With a login" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : parentRows.filter((r) => r.hasAccount).length}
          </p>
        </Card>
        <Card>
          <CardHeader title="Without a login" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : withoutLogin}
          </p>
          {!loading && unlinked.length > 0 && (
            <p className="mt-1 text-[11px] text-amber-200">
              +{unlinked.length} not linked to any guardian
            </p>
          )}
        </Card>
        <Card>
          <CardHeader title="Administrators" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : admins.length}
          </p>
        </Card>
      </div>

      {/* ---- form (a popup: it used to open at the top of the page,
          out of sight for an admin far down the parents' list) ---- */}
      {form && (
        <Modal
          id="account-form"
          size="lg"
          title={form.mode === "create" ? "New account" : "Edit account"}
          description={form.user?.email}
          onClose={closeForm}
        >
          {problem && <ProblemBox text={problem} />}
          <form onSubmit={save} className="grid gap-3 sm:grid-cols-2">
            {/* Pick the guardian first - email and name are filled
                in from it. The email used to be typed by hand, and
                if it did not match the ERPNext record the school
                ended up with two different addresses. */}
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                Guardian (from {recordsName})
              </span>
              <select
                value={picked}
                onChange={(e) => setPicked(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white outline-none focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
              >
                <option value="" className="bg-[#0b0a2a]">
                  Not linked — no child records
                </option>
                {(guardians || []).map((g) => (
                  <option key={g.id} value={g.id} className="bg-[#0b0a2a]">
                    {g.name} · {g.students} student
                    {g.students === 1 ? "" : "s"}
                    {g.email ? "" : `  (no email in ${recordsName})`}
                  </option>
                ))}
              </select>
              <input type="hidden" name="parent_id" value={picked} />

              {chosen ? (
                <span className="mt-1.5 block font-mono text-[11px] text-text-secondary/70">
                  {chosen.id} — this Guardian ID links the login automatically.
                </span>
              ) : (
                <span className="mt-1.5 block text-[11px] leading-4 text-text-secondary/70">
                  Without a guardian picked, Vocira finds no children for this login.
                </span>
              )}
            </label>

            {/* The guardian has no email in ERPNext */}
            {chosen && !chosen.email && (
              <div className="flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/[0.07] px-3 py-2.5 text-[11px] leading-5 text-amber-100 sm:col-span-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  <span className="font-semibold">
                    {chosen.name} has no email address in {recordsName}.
                  </span>{" "}
                  {recordsKind === "erpnext" ? (
                    <>
                      Set it first in ERPNext (Education → Guardian → {chosen.name} → Email Address), then reload this
                      page.
                    </>
                  ) : (
                    <>Set it first in {recordsName}, then reload this page.</>
                  )}
                  The login email must match the guardian record.
                </span>
              </div>
            )}

            {/*
                The email can be changed in both cases.

                While creating, it fills in from the guardian and is
                readOnly - enforcing a match there is right.

                While editing it is NOT readOnly: a parent's address
                can change, or an older account's email may not match
                ERPNext and need fixing. Locking it would leave the
                admin no way through.
            */}
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                Email
              </span>
              <input
                name="email"
                type="email"
                required
                readOnly={form.mode === "create" && Boolean(chosen?.email)}
                value={emailValue}
                onChange={(e) => setEmailTyped(e.target.value)}
                placeholder="parent@example.com"
                className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-text-secondary/60 ${
                  form.mode === "create" && chosen?.email
                    ? "cursor-default border-white/[0.06] bg-white/[0.02] text-text-secondary"
                    : "border-white/10 bg-white/[0.04] text-white focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
                }`}
              />

              {form.mode === "create" ? (
                <span className="mt-1.5 block text-[11px] leading-4 text-text-secondary/70">
                  {chosen?.email
                    ? `Taken from the guardian record in ${recordsName}.`
                    : "No guardian selected — type the email manually."}
                </span>
              ) : chosen?.email && chosen.email !== emailValue ? (
                // Only when something actually differs - otherwise
                // this is a button that does nothing
                <button
                  type="button"
                  onClick={() => setEmailTyped(chosen.email)}
                  className="mt-1.5 inline-flex items-center gap-1.5 rounded-lg bg-amber-400/10 px-2 py-1 text-[11px] font-medium text-amber-200 transition-colors hover:bg-amber-400/20"
                >
                  <AlertTriangle className="h-3 w-3" />
                  Use {chosen.email} from {recordsName}
                </button>
              ) : (
                <span className="mt-1.5 block text-[11px] leading-4 text-text-secondary/70">
                  Changing this changes how they log in.
                </span>
              )}
            </label>

            <Field
              label="Full name"
              name="name"
              required
              value={nameValue}
              onChange={(e) => setNameTyped(e.target.value)}
              placeholder="Muhammad Ahmed"
            />

            {form.mode === "create" && (
              <PasswordField
                label="Password"
                name="password"
                required
                minLength={8}
                placeholder="At least 8 characters"
              />
            )}

            {/* No role to pick: a login set up or edited here is a
                guardian's. An administrator's row keeps its admin role. */}
            <input type="hidden" name="role" value={form.user?.role === "admin" ? "admin" : "guardian"} />

            <div className="flex items-end justify-end gap-2 sm:col-span-2">
              <Button variant="outline" type="button" onClick={closeForm}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy === "save"}>
                {busy === "save"
                  ? "Saving…"
                  : form.mode === "create"
                    ? "Create account"
                    : "Save changes"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* ---- password reset (a popup too) ---- */}
      {pwFor && (
        <Modal
          id="password-form"
          title="Reset password"
          description={`A new password for ${pwFor.email}. The old one stops working immediately.`}
          onClose={closePassword}
        >
          {problem && <ProblemBox text={problem} />}
          <form onSubmit={resetPassword} className="flex flex-wrap items-end gap-3">
            <div className="min-w-[240px] flex-1">
              <PasswordField
                label="New password"
                name="password"
                required
                minLength={8}
                placeholder="At least 8 characters"
              />
            </div>
            <div className="flex gap-2 pb-0.5">
              <Button variant="outline" type="button" onClick={closePassword}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy === "pw"}>
                {busy === "pw" ? "Saving…" : "Set password"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* "Password changed…" where it is seen - the page may be scrolled far down */}
      {notice && !error && (
        <div
          id="accounts-notice"
          role="status"
          className="fixed bottom-6 right-6 z-[95] max-w-sm rounded-xl border border-emerald-400/30 bg-bg-secondary px-4 py-3 text-xs text-emerald-200 shadow-card"
        >
          {notice}
        </div>
      )}

      {/* ---- do alag list: admins aur parents ----

          The two used to be mixed into one table. They are entirely
          different things: an admin runs the panel, a parent asks
          about their child's data. And the "Guardian ID" column is
          meaningless for an admin - they have no children. */}

      <AccountTable
        title="Administrators"
        description="These accounts can open this panel"
        rows={filteredAdmins}
        totalCount={admins.length}
        showGuardian={false}
        search={adminSearch}
        onSearchChange={setAdminSearch}
        searchPlaceholder="Search administrators..."
        emptyText={adminNeedle ? "No administrators match this search." : "No administrators."}
        busy={busy}
        isOpen={openSections.has("admins")}
        onToggle={() => toggleSection("admins")}
        onEdit={(u) => { setPwFor(null); setPicked(u.parent_id || ""); setEmailTyped(u.email); setNameTyped(u.name); setForm({ mode: "edit", user: u }); }}
        onPassword={(u) => { setForm(null); setPwFor(u); }}
        onDelete={remove}
      />

      <AccountTable
        title="Parents"
        description={`One row per guardian in ${recordsName} — new ones appear here on their own`}
        rows={filteredParents}
        totalCount={parentRows.length}
        showGuardian
        guardianById={guardianById}
        search={parentSearch}
        onSearchChange={setParentSearch}
        searchPlaceholder="Search parents..."
        emptyText={parentNeedle ? "No parents match this search." : `No guardians in ${recordsName} yet.`}
        recordsName={recordsName}
        busy={busy}
        isOpen={openSections.has("parents")}
        onToggle={() => toggleSection("parents")}
        onEdit={(u) => { setPwFor(null); setPicked(u.parent_id || ""); setEmailTyped(u.email); setNameTyped(u.name); setForm({ mode: "edit", user: u }); }}
        onPassword={(u) => { setForm(null); setPwFor(u); }}
        onSetupLogin={(u) => setupLogin(u.parent_id)}
        onDelete={remove}
      />
    </div>
  );
}

/**
 * A list of accounts.
 *
 * Admins and parents share the same structure; only the "Guardian
 * ID" column differs - an admin has no children, so that column is
 * meaningless for them.
 */
function AccountTable({
  recordsName = "the school's records",
  title,
  guardianById,
  description,
  rows,
  totalCount,
  showGuardian,
  search,
  onSearchChange,
  searchPlaceholder,
  emptyText,
  busy,
  isOpen,
  onToggle,
  onEdit,
  onPassword,
  onSetupLogin,
  onDelete,
}) {
  const columns = showGuardian ? 6 : 5;
  const count = totalCount ?? rows.length;
  const filtering = totalCount !== undefined && totalCount !== rows.length;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onToggle}
          className="text-left"
        >
          <CardHeader
            title={`${title} (${filtering ? `${rows.length} of ${count}` : count})`}
            description={description}
          />
        </button>

        <div className="flex items-center gap-2">
          {/* Its own search - filters only this table, not the other one. */}
          <div className="relative w-56 shrink-0">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary">
              <Search className="h-3.5 w-3.5" />
            </span>
            <input
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder || "Search name or email..."}
              className="w-full rounded-xl border border-white/10 bg-white/[0.04] py-2.5 pl-8 pr-8 text-xs text-white placeholder:text-text-secondary/70 outline-none transition-colors focus:border-accent-primary/50 focus:bg-white/[0.07] focus:ring-2 focus:ring-accent-primary/40"
            />
            {search && (
              <button
                type="button"
                onClick={() => onSearchChange("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-text-secondary transition-colors hover:bg-white/10 hover:text-white"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={onToggle}
            className="shrink-0 rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-white/10 hover:text-white"
            aria-label={isOpen ? "Collapse" : "Expand"}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${
                isOpen ? "rotate-180" : ""
              }`}
            />
          </button>
        </div>
      </div>

      {isOpen && (
      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH>Email</TH>
            <TH>Role</TH>
            {showGuardian && <TH>Guardian ID</TH>}
            <TH>Created</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {rows.length === 0 && (
            <TR>
              <TD colSpan={columns} className="py-6 text-center text-xs text-text-secondary">
                {emptyText}
              </TD>
            </TR>
          )}

          {rows.map((u) => (
            <TR key={u.key ?? u.user_id}>
              <TD className="text-xs font-medium text-white">
                {u.name || <span className="text-text-secondary/60">—</span>}
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {u.email || (
                  <span className="italic text-text-secondary/60">no login yet</span>
                )}
                {(() => {
                  // Flag it when the login email differs from the
                  // ERPNext guardian record. It is not a fault -
                  // VOCIRA links by parent_id, not by email - but two
                  // addresses for one parent confuses the school.
                  const g = guardianById?.[u.parent_id];
                  if (!g?.email || g.email === u.email) return null;
                  return (
                    <span
                      title={`${recordsName} has ${g.email}`}
                      className="ml-2 inline-flex items-center gap-1 rounded-md bg-amber-400/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-200"
                    >
                      <AlertTriangle className="h-2.5 w-2.5" />
                      differs from {recordsName}
                    </span>
                  );
                })()}
              </TD>
              <TD>
                {u.hasAccount === false ? (
                  <Badge label="no login yet" variant="warning" />
                ) : (
                  <Badge
                    label={u.role || "—"}
                    variant={u.role === "admin" ? "success" : "neutral"}
                  />
                )}
              </TD>

              {showGuardian && (
                <TD className="whitespace-nowrap font-mono text-[11px]">
                  {u.parent_id ? (
                    <span className="text-text-secondary">{u.parent_id}</span>
                  ) : u.role === "guardian" ? (
                    <Badge label="not linked" variant="warning" />
                  ) : (
                    <span className="text-text-secondary">—</span>
                  )}
                </TD>
              )}

              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {u.created_at ? formatTime(u.created_at) : "—"}
              </TD>
              <TD className="text-right">
                {u.hasAccount === false ? (
                  // No account exists yet for this guardian - there is
                  // nothing to edit, reset, or delete, only to create.
                  <Button
                    variant="outline"
                    onClick={() => onSetupLogin(u)}
                    className="ml-auto !px-3 !py-1.5 !text-[11px]"
                  >
                    <KeyRound className="h-3 w-3" />
                    Set password
                  </Button>
                ) : (
                  <div className="flex justify-end gap-1">
                    <IconButton title="Edit" onClick={() => onEdit(u)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </IconButton>
                    <IconButton title="Reset password" onClick={() => onPassword(u)}>
                      <KeyRound className="h-3.5 w-3.5" />
                    </IconButton>
                    <IconButton
                      title="Delete"
                      danger
                      disabled={busy === u.user_id}
                      onClick={() => onDelete(u)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </IconButton>
                  </div>
                )}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
      )}
    </Card>
  );
}

function ProblemBox({ text }) {
  return (
    <div className="mb-3 rounded-xl border border-red-400/30 bg-red-400/[0.07] px-3 py-2 text-xs text-red-200">
      {text}
    </div>
  );
}

function Field({ label, hint, ...props }) {
  // On a readOnly field the cursor and colour show that it was
  // filled in automatically - otherwise the admin keeps typing and
  // nothing happens.
  const locked = props.readOnly;

  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
        {label}
      </span>
      <input
        {...props}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-text-secondary/60 ${
          locked
            ? "cursor-default border-white/[0.06] bg-white/[0.02] text-text-secondary"
            : "border-white/10 bg-white/[0.04] text-white focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
        }`}
      />
      {hint && (
        <span className="mt-1.5 block text-[11px] leading-4 text-text-secondary/70">
          {hint}
        </span>
      )}
    </label>
  );
}

/**
 * A password field with a reveal button.
 *
 * The admin is typing a password for someone else, so being able to
 * see it matters - otherwise a typo only surfaces when the parent
 * cannot log in.
 *
 * The login page already works this way.
 */
function PasswordField({ label, ...props }) {
  const [shown, setShown] = useState(false);

  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
        {label}
      </span>

      <div className="relative">
        <input
          {...props}
          type={shown ? "text" : "password"}
          className="w-full rounded-xl border border-white/10 bg-white/[0.04] py-2.5 pl-3 pr-11 text-sm text-white placeholder:text-text-secondary/60 outline-none transition-colors focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
        />

        <button
          type="button"
          onClick={() => setShown((on) => !on)}
          title={shown ? "Hide password" : "Show password"}
          aria-label={shown ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/40"
        >
          {shown ? (
            <EyeOff className="h-[18px] w-[18px]" />
          ) : (
            <Eye className="h-[18px] w-[18px]" />
          )}
        </button>
      </div>
    </label>
  );
}

function IconButton({ children, danger, ...props }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 text-text-secondary transition-colors disabled:opacity-50 ${
        danger
          ? "hover:border-red-400/40 hover:bg-red-400/10 hover:text-red-300"
          : "hover:bg-white/10 hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}
