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

import { useState } from "react";
import {
  AlertTriangle,
  Eye,
  EyeOff,
  KeyRound,
  Link2Off,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";

import Badge from "@/app/admin/_components/ui/Badge";
import Button from "@/app/admin/_components/ui/Button";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";

const EMPTY = { users: [], total: 0, linked: 0 };
const BASE = "/auth/admin/users";

export default function UsersPage() {
  const { data, loading, error, reload } = useAdminData(BASE, EMPTY);
  const { data: roles } = useAdminData(`${BASE}/roles`, []);

  // ERPNext's guardians - to pick from a list when creating an
  // account. The Guardian ID used to be typed by hand: one character
  // out of place and the account reached no child, and the mistake
  // only surfaced when the parent complained.
  const { data: guardians } = useAdminData("/livekit/admin/guardians", []);

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

  const users = data.users || [];

  // Admins and parents are two entirely different things - one runs
  // the panel, the other asks about their child's data. Keeping both
  // in one list only confused both.
  const admins = users.filter((u) => u.role === "admin");
  const parents = users.filter((u) => u.role !== "admin");

  const unlinked = parents.filter((u) => u.role === "guardian" && !u.parent_id);

  const chosen = (guardians || []).find((g) => g.id === picked) || null;

  // Each row's ERPNext guardian record - so we can show whether the
  // login email matches it.
  const guardianById = Object.fromEntries(
    (guardians || []).map((g) => [g.id, g])
  );

  const emailValue =
    emailTyped !== null ? emailTyped : chosen?.email || "";

  const nameValue =
    nameTyped !== null
      ? nameTyped
      : chosen?.name || form?.user?.name || "";

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

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Accounts
          </h1>
          <p className="mt-1 text-xs text-text-secondary">
            Admin and parent logins for Vocira. These are separate from
            ERPNext users.
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button onClick={() => { setPicked(""); setEmailTyped(null); setNameTyped(null); setForm({ mode: "create", user: null }); }}>
            <Plus className="h-3.5 w-3.5" />
            Add account
          </Button>
        </div>
      </div>

      {problem && (
        <div className="rounded-xl border border-red-400/30 bg-red-400/[0.07] px-3 py-2 text-xs text-red-200">
          {problem}
        </div>
      )}

      {(error || notice) && !problem && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
          {error || notice}
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

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader title="Parents" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : parents.length}
          </p>
        </Card>
        <Card>
          <CardHeader title="Linked to a guardian" />
          <p className="text-2xl font-semibold text-white">
            {loading ? "…" : data.linked}
          </p>
          {!loading && unlinked.length > 0 && (
            <p className="mt-1 text-[11px] text-amber-200">
              {unlinked.length} not linked
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

      {/* ---- form ---- */}
      {form && (
        <Card>
          <div className="mb-4 flex items-start justify-between gap-2">
            <div>
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                {form.mode === "create" ? "New account" : "Edit account"}
              </h2>
              {form.user && (
                <p className="mt-1.5 text-xs text-text-secondary/75">
                  {form.user.email}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => setForm(null)}
              className="rounded-lg border border-white/10 p-1.5 text-text-secondary hover:bg-white/5 hover:text-white"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <form onSubmit={save} className="grid gap-3 sm:grid-cols-2">
            {/* Pick the guardian first - email and name are filled
                in from it. The email used to be typed by hand, and
                if it did not match the ERPNext record the school
                ended up with two different addresses. */}
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                Guardian (from ERPNext)
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
                    {g.email ? "" : "  (no email in ERPNext)"}
                  </option>
                ))}
              </select>
              <input type="hidden" name="parent_id" value={picked} />

              {chosen && (
                <span className="mt-1.5 block font-mono text-[11px] text-text-secondary/70">
                  {chosen.id}
                </span>
              )}
            </label>

            {/* The guardian has no email in ERPNext */}
            {chosen && !chosen.email && (
              <div className="flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/[0.07] px-3 py-2.5 text-[11px] leading-5 text-amber-100 sm:col-span-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  <span className="font-semibold">
                    {chosen.name} has no email address in ERPNext.
                  </span>{" "}
                  Set it first in ERPNext (Education → Guardian →{" "}
                  {chosen.name} → Email Address), then reload this page.
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
                    ? "Taken from the guardian record in ERPNext."
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
                  Use {chosen.email} from ERPNext
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

            <Field
              label="Guardian ID (ERPNext)"
              name="parent_id"
              defaultValue={form.user?.parent_id || ""}
              placeholder="EDU-GRD-2026-00002"
              hint="Links this login to a guardian record. Without it, Vocira finds no children."
            />

            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                Role
              </span>
              <select
                name="role"
                defaultValue={form.user?.role || "guardian"}
                className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white outline-none focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
              >
                {(roles || []).map((r) => (
                  <option key={r.role_id} value={r.name} className="bg-[#0b0a2a]">
                    {r.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-end justify-end gap-2 sm:col-span-2">
              <Button variant="outline" type="button" onClick={() => setForm(null)}>
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
        </Card>
      )}

      {/* ---- password reset ---- */}
      {pwFor && (
        <Card>
          <CardHeader
            title="Reset password"
            description={`A new password for ${pwFor.email}. The old one stops working immediately.`}
          />
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
              <Button variant="outline" type="button" onClick={() => setPwFor(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy === "pw"}>
                {busy === "pw" ? "Saving…" : "Set password"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* ---- do alag list: admins aur parents ----

          The two used to be mixed into one table. They are entirely
          different things: an admin runs the panel, a parent asks
          about their child's data. And the "Guardian ID" column is
          meaningless for an admin - they have no children. */}

      <AccountTable
        title="Administrators"
        description="These accounts can open this panel"
        rows={admins}
        loading={loading}
        showGuardian={false}
        emptyText="No administrators."
        busy={busy}
        onEdit={(u) => { setPwFor(null); setPicked(u.parent_id || ""); setEmailTyped(u.email); setNameTyped(u.name); setForm({ mode: "edit", user: u }); }}
        onPassword={(u) => { setForm(null); setPwFor(u); }}
        onDelete={remove}
      />

      <AccountTable
        title="Parents"
        description="Vocira logins — not the same as ERPNext users"
        rows={parents}
        loading={loading}
        showGuardian
        guardianById={guardianById}
        emptyText="No parent accounts yet."
        busy={busy}
        onEdit={(u) => { setPwFor(null); setPicked(u.parent_id || ""); setEmailTyped(u.email); setNameTyped(u.name); setForm({ mode: "edit", user: u }); }}
        onPassword={(u) => { setForm(null); setPwFor(u); }}
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
  title,
  guardianById,
  description,
  rows,
  loading,
  showGuardian,
  emptyText,
  busy,
  onEdit,
  onPassword,
  onDelete,
}) {
  const columns = showGuardian ? 6 : 5;

  return (
    <Card>
      <CardHeader
        title={`${title}${loading ? "" : ` (${rows.length})`}`}
        description={description}
      />

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
          {loading && (
            <TR>
              <TD colSpan={columns} className="py-6 text-center text-xs text-text-secondary">
                Loading…
              </TD>
            </TR>
          )}

          {!loading && rows.length === 0 && (
            <TR>
              <TD colSpan={columns} className="py-6 text-center text-xs text-text-secondary">
                {emptyText}
              </TD>
            </TR>
          )}

          {rows.map((u) => (
            <TR key={u.user_id}>
              <TD className="text-xs font-medium text-white">{u.name}</TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {u.email}
                {(() => {
                  // Flag it when the login email differs from the
                  // ERPNext guardian record. It is not a fault -
                  // VOCIRA links by parent_id, not by email - but two
                  // addresses for one parent confuses the school.
                  const g = guardianById?.[u.parent_id];
                  if (!g?.email || g.email === u.email) return null;
                  return (
                    <span
                      title={`ERPNext has ${g.email}`}
                      className="ml-2 inline-flex items-center gap-1 rounded-md bg-amber-400/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-200"
                    >
                      <AlertTriangle className="h-2.5 w-2.5" />
                      differs from ERPNext
                    </span>
                  );
                })()}
              </TD>
              <TD>
                <Badge
                  label={u.role || "—"}
                  variant={u.role === "admin" ? "success" : "neutral"}
                />
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
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </Card>
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
