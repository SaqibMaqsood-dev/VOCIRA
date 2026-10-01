"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Eye, EyeOff } from "lucide-react";

import { clearSession, saveSession } from "@/lib/session";
import { SUPER_ADMIN_LOGIN, loginPath } from "@/lib/school";
import { useSchoolOfPage, useSite } from "@/lib/site";
import FullScreenLoader from "@/components/FullScreenLoader";

// How long the full-screen loader stays up after a successful login
// before the redirect actually fires. Long enough to read as a
// deliberate transition, short enough that it never feels like a
// delay - the login itself already finished before this starts.
const REDIRECT_DELAY_MS = 1000;

/**
 * Read the role out of the JWT.
 *
 * This only picks a destination (admin -> /admin, otherwise
 * /dashboard). The real gate is on the backend: require_admin
 * returns 403 for a parent's token. So the signature does not need
 * checking here - and could not be, without a library.
 *
 * A malformed token gives null, and that goes to /dashboard.
 */
function readRoleFromToken(token) {
  try {
    const part = token.split(".")[1];
    if (!part) return null;

    // JWT uses base64url; atob expects base64
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);

    const claims = JSON.parse(atob(padded));
    return claims?.role || null;
  } catch {
    return null;
  }
}

export default function LoginPage() {
  /*
   * Where this sign-in is. Vocira's main address is the super admin's
   * alone; parents and school staff sign in at their own school's
   * address, and the server checks the account belongs to it.
   *   site === null        -> still reading the address
   *   school === undefined -> looking the school up
   *   school === null      -> the address is no school's
   */
  const site = useSite();
  const school = useSchoolOfPage(site?.subdomain);
  const atSchool = Boolean(site?.isSchool);
  const ready = site !== null && (!atSchool || Boolean(school));

  // One page, two doors: a school's sign-in is its /login; the super
  // admin's is /super_admin_login on the plain address, whose /login offers
  // nothing (Vocira's own site has no sign-in for its visitors). The wrong
  // door sends you on: to Vocira's home. A school's address never shows
  // /super_admin_login at all - the server answers it "not found"
  // (proxy.js); sending it to the school's /login is only a fallback.
  const pathname = usePathname();
  const wrongDoor =
    site !== null && (atSchool ? pathname === SUPER_ADMIN_LOGIN : pathname !== SUPER_ADMIN_LOGIN);

  useEffect(() => {
    if (wrongDoor) window.location.replace(atSchool ? "/login" : "/");
  }, [wrongDoor, atSchool]);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Set only once login has actually succeeded - this is what shows
  // the full-screen transition and holds the redirect for a moment
  // instead of jumping straight to the next page.
  const [redirecting, setRedirecting] = useState(false);
  const [redirectRole, setRedirectRole] = useState(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL;

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");

    if (!API_URL) {
      setError(
        "API URL is not configured. Please check your .env.local file."
      );
      return;
    }

    if (!username.trim() || !password) {
      setError("Please enter your username and password.");
      return;
    }

    if (!ready) {
      return;
    }

    setLoading(true);

    try {
      // FastAPI OAuth2PasswordRequestForm
      // requires application/x-www-form-urlencoded

      const formData = new URLSearchParams();

      formData.append("username", username.trim());
      formData.append("password", password);
      // the school this page belongs to - none on the main address
      if (atSchool) {
        formData.append("school", school.id);
      }

      console.log("API_URL:", API_URL);
      console.log("LOGIN URL:", `${API_URL}/auth/login`);

      const response = await fetch(
        `${API_URL}/auth/login`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/x-www-form-urlencoded",
          },
          body: formData.toString(),
        }
      );

      /*
       * Parse backend response
       */

      let data;

      try {
        data = await response.json();
      } catch {
        setError(
          "The server returned an invalid response."
        );
        return;
      }

      console.log("Login response:", data);

      /*
       * LOGIN FAILURE
       *
       * Invalid credentials are a normal UI state.
       * Do not throw an Error here.
       */

      if (!response.ok) {
        if (typeof data?.detail === "string") {
          setError(data.detail);
          return;
        }

        if (Array.isArray(data?.detail)) {
          const message = data.detail
            .map((item) => item.msg)
            .filter(Boolean)
            .join(", ");

          setError(
            message || "Login validation failed."
          );

          return;
        }

        setError(
          "Login failed. Please check your credentials."
        );

        return;
      }

      /*
       * LOGIN SUCCESS
       */

      if (!data?.access_token) {
        setError(
          "Login succeeded but no access token was returned."
        );
        return;
      }

      /*
       * Save the session.
       *
       * The refresh token matters now: the backend returns one, and
       * authFetch uses it to renew the access token when it expires.
       * Login used to store whatever came back, but nothing ever
       * came back and nothing ever renewed, so a session simply
       * ended after ACCESS_TOKEN_EXPIRE_MINUTES.
       *
       * The whole response used to be written to "auth_response" as
       * well. Nothing read it, and it put a second copy of the
       * refresh token in localStorage - so it is no longer stored.
       */

      saveSession(data);

      /*
       * Notify other frontend components
       * that authentication state changed.
       */

      window.dispatchEvent(
        new Event("auth-change")
      );

      /*
       * Login succeeded - route by role.
       *
       * The role lives inside the JWT. It is read here only to pick
       * a destination - the real gate is on the backend
       * (require_admin, which returns 403 for a parent's token). So
       * the token's signature does not need verifying here.
       */

      const role = readRoleFromToken(data.access_token);

      if (role) {
        localStorage.setItem("role", role);
      }

      /*
       * Show the full-screen transition and hold the redirect for a
       * moment instead of jumping straight to the next page. The
       * destination itself is unchanged - only when we navigate to
       * it changes.
       */

      setRedirectRole(role);
      setRedirecting(true);

      setTimeout(() => {
        window.location.href =
          role === "super_admin"
            ? "/superadmin"
            : role === "admin"
              ? "/admin"
              : "/dashboard";
      }, REDIRECT_DELAY_MS);

      return;

    } catch (error) {
      /*
       * Only unexpected/network errors reach here.
       */

      console.error("Login error:", error);

      if (error instanceof TypeError) {
        setError(
          "Unable to connect to the server. Please make sure the API Gateway is running."
        );
      } else {
        setError(
          "Something went wrong. Please try again."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  /*
   * LOGOUT
   *
   * Removes all locally stored authentication data.
   */

  const handleLogout = () => {
    clearSession();

    /*
     * Notify navbar/components that the user logged out.
     */

    window.dispatchEvent(
      new Event("auth-change")
    );

    /*
     * Redirect to login.
     */

    window.location.href = loginPath();
  };

  // nothing of the sign-in shows behind a door that is about to send you on
  if (site === null || wrongDoor) {
    return <div className="page-shell" />;
  }

  return (
    <>
      {redirecting && (
        <FullScreenLoader
          subLabel={
            redirectRole === "super_admin"
              ? "Taking you to the schools"
              : redirectRole === "admin"
              ? "Taking you to the admin panel"
              : "Taking you to your calls"
          }
        />
      )}

    <div className="page-shell flex items-center">
      <div className="grid h-full items-center gap-8 lg:grid-cols-2">

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.55,
            ease: "easeOut",
          }}
          className="relative"
        >
          <div className="pointer-events-none absolute -left-16 -top-10 size-56 rounded-full bg-accent-secondary/14 blur-3xl" />

          <h1 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            {site && !atSchool ? "Vocira super admin." : "Welcome Back."}
          </h1>

          <p id="login-where" className="mt-3 text-lg text-text-secondary">
            {site === null
              ? " "
              : !atSchool
              ? "Sign in to manage the schools."
              : school
              ? `Sign in to ${school.name}.`
              : "Sign into your account."}
          </p>

          <div className="mt-8 glass p-6">
            <p className="text-sm leading-7 text-text-secondary">
              {site && !atSchool
                ? "Add schools, give each its own address, and connect their records. Parents and school staff sign in at their own school's address, not here."
                : "Continue your voice sessions and access your call history."}
            </p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.55,
            ease: "easeOut",
            delay: 0.06,
          }}
          className="mx-auto w-full max-w-md"
        >
          <div className="glass p-6">

            <h2 className="text-2xl font-semibold text-text-primary">
              {site && !atSchool ? "Super admin sign in" : "Sign in"}
            </h2>

            <p className="mt-2 text-sm text-text-secondary">
              {site && !atSchool
                ? "Only the Vocira super admin signs in here."
                : school
                ? `Enter your ${school.name} account.`
                : "Enter your credentials to access Vocira."}
            </p>

            {atSchool && school === null ? (
              <div id="login-unknown-school" className="mt-6 rounded-xl border border-white/10 bg-white/[0.04] p-4 text-sm text-text-secondary">
                This is not a school&apos;s address. Please open the sign-in link your school shares.
              </div>
            ) : (
            <form
              onSubmit={handleSubmit}
              className="mt-6 space-y-5"
            >

              {/* Username */}
              <div>
                <label
                  htmlFor="username"
                  className="mb-2 block text-sm font-medium text-text-primary"
                >
                  Username
                </label>

                <input
                  id="username"
                  name="username"
                  type="text"
                  placeholder="Your username"
                  value={username}
                  onChange={(event) =>
                    setUsername(event.target.value)
                  }
                  disabled={loading}
                  required
                  autoComplete="username"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-text-primary outline-none transition placeholder:text-text-secondary/60 focus:border-accent-secondary focus:ring-2 focus:ring-accent-secondary/20 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="password"
                  className="mb-2 block text-sm font-medium text-text-primary"
                >
                  Password
                </label>

                <div className="relative">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Your password"
                    value={password}
                    onChange={(event) =>
                      setPassword(event.target.value)
                    }
                    disabled={loading}
                    required
                    autoComplete="current-password"
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 pr-12 text-sm text-text-primary outline-none transition placeholder:text-text-secondary/60 focus:border-accent-secondary focus:ring-2 focus:ring-accent-secondary/20 disabled:cursor-not-allowed disabled:opacity-60"
                  />

                  <button
                    type="button"
                    onClick={() =>
                      setShowPassword((visible) => !visible)
                    }
                    disabled={loading}
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                    tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-text-secondary transition hover:text-accent-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-secondary/40 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {showPassword ? (
                      <EyeOff className="size-[18px]" />
                    ) : (
                      <Eye className="size-[18px]" />
                    )}
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="text-sm text-red-400">
                  {error}
                </div>
              )}

              {/* Login button - matches the style in AuthForm.jsx:
                  a glass surface with an accent glow on both sides.
                  This used to be white text on bg-accent-secondary
                  (pale cyan), which had weak contrast and did not
                  match the rest of the app. */}
              <motion.button
                type="submit"
                disabled={loading || !ready}
                whileHover={loading ? {} : { y: -2 }}
                whileTap={loading ? {} : { scale: 0.98 }}
                className="group relative w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="pointer-events-none absolute -left-28 top-1/2 h-28 w-28 -translate-y-1/2 rotate-12 bg-accent-primary/40 blur-2xl transition-opacity group-hover:opacity-90" />
                <span className="pointer-events-none absolute -right-28 top-1/2 h-28 w-28 -translate-y-1/2 -rotate-12 bg-accent-secondary/22 blur-2xl transition-opacity group-hover:opacity-90" />

                <span className="relative inline-flex items-center justify-center gap-2">
                  {loading && (
                    <span className="size-4 animate-spin rounded-full border-2 border-white/25 border-t-accent-secondary" />
                  )}
                  {loading ? "Signing in..." : "Login"}
                </span>
              </motion.button>

            </form>
            )}

            {/*
              Self-signup is deliberately absent.

              A parent's account is tied to an ERPNext Guardian
              record (parent_id). The school creates that ID - a
              parent neither knows it nor can prove it. A
              self-created account would either be useless (it
              reaches no child) or - if parent_id could be typed in -
              would open another family's data.

              So the school issues the account. This link used to
              point at /signup, which does not exist (404).
            */}
            <div id="login-footer" className="mt-6 text-center text-sm text-text-secondary">
              {site && !atSchool
                ? "Parent or school staff? Sign in at your school's own address."
                : "Need an account? Please contact the school office."}
            </div>

          </div>
        </motion.div>
      </div>
    </div>
    </>
  );
}