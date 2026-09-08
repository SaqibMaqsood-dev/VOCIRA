"use client";

/**
 * Parents ke accounts.
 *
 * Pehle VOCIRA ke accounts kahin se bhi nazar nahi aate thay. Log
 * ERPNext ke Users mein dhoondte thay aur wahan milte hi nahi -
 * kyunke wo Postgres mein hain, ERPNext mein nahi. Na account
 * banane ka raasta tha, na password badalne ka.
 *
 * parent_id sab se ahem field hai: wahi ERPNext ke Guardian record
 * se joRta hai. Us ke baghair account ban to jata hai magar us ko
 * koi bachcha nahi milta - is liye us ki kami saaf dikhayi jati hai.
 */

import { useState } from "react";
import {
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

  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState("");

  const [form, setForm] = useState(null);   // { mode, user }
  const [pwFor, setPwFor] = useState(null); // password reset ke liye

  const users = data.users || [];

  // Admin aur parent do bilkul alag cheezein hain - ek panel
  // chalata hai, doosra apne bachche ka data poochta hai. Ek hi
  // list mein dono rakhna dono ko ulajha deta tha.
  const admins = users.filter((u) => u.role === "admin");
  const parents = users.filter((u) => u.role !== "admin");

  const unlinked = parents.filter((u) => u.role === "guardian" && !u.parent_id);

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
        say(`${made.email} ka account ban gaya`);
      } else {
        await adminFetch(`${BASE}/${form.user.user_id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: payload.name,
            parent_id: payload.parent_id,
            role: payload.role,
          }),
        });
        say(`${form.user.email} update ho gaya`);
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
      say(`${pwFor.email} ka password badal diya`);
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
      say(`${user.email} hata diya`);
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
            Parent accounts
          </h1>
          <p className="mt-1 text-xs text-text-secondary">
            Vocira logins. These are separate from ERPNext users.
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button onClick={() => setForm({ mode: "create", user: null })}>
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
            {form.mode === "create" && (
              <Field
                label="Email"
                name="email"
                type="email"
                required
                placeholder="parent@example.com"
              />
            )}

            <Field
              label="Full name"
              name="name"
              required
              defaultValue={form.user?.name || ""}
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

          Pehle dono ek hi table mein mile hue thay. Ye do bilkul
          alag cheezein hain: admin panel chalata hai, parent apne
          bachche ka data poochta hai. Aur admin ke liye "Guardian
          ID" ka column bemani hai - us ke bachche hote hi nahi. */}

      <AccountTable
        title="Administrators"
        description="These accounts can open this panel"
        rows={admins}
        loading={loading}
        showGuardian={false}
        emptyText="No administrators."
        busy={busy}
        onEdit={(u) => { setPwFor(null); setForm({ mode: "edit", user: u }); }}
        onPassword={(u) => { setForm(null); setPwFor(u); }}
        onDelete={remove}
      />

      <AccountTable
        title="Parents"
        description="Vocira logins — not the same as ERPNext users"
        rows={parents}
        loading={loading}
        showGuardian
        emptyText="No parent accounts yet."
        busy={busy}
        onEdit={(u) => { setPwFor(null); setForm({ mode: "edit", user: u }); }}
        onPassword={(u) => { setForm(null); setPwFor(u); }}
        onDelete={remove}
      />
    </div>
  );
}

/**
 * Accounts ki ek list.
 *
 * Admins aur parents ka dhaancha ek hi hai, sirf "Guardian ID" ka
 * column farq karta hai - admin ke bachche hote hi nahi, is liye
 * us ke liye wo column bemani hai.
 */
function AccountTable({
  title,
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
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
        {label}
      </span>
      <input
        {...props}
        className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white placeholder:text-text-secondary/60 outline-none transition-colors focus:border-accent-primary/50 focus:ring-2 focus:ring-accent-primary/30"
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
 * Password ka field, dekhne ke button ke sath.
 *
 * Admin doosre ke liye password type kar raha hota hai, is liye
 * use dekhna zaroori hai - warna typo ka pata tab chalta hai jab
 * parent login na kar sake.
 *
 * Login page par yahi tareeqa pehle se hai.
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
