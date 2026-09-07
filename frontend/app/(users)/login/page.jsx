"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff } from "lucide-react";

/**
 * JWT ke andar se role padhein.
 *
 * Ye sirf raasta chunne ke liye hai (admin -> /admin, warna
 * /dashboard). Asli rok backend par hai: require_admin parent ke
 * token par 403 deta hai. Is liye yahan signature jaanchna zaroori
 * nahi - aur bina library ke ho bhi nahi sakta.
 *
 * Token kharab ho to null - us surat mein /dashboard chala jata hai.
 */
function readRoleFromToken(token) {
  try {
    const part = token.split(".")[1];
    if (!part) return null;

    // JWT base64url use karta hai; atob base64 chahta hai
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);

    const claims = JSON.parse(atob(padded));
    return claims?.role || null;
  } catch {
    return null;
  }
}

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

    setLoading(true);

    try {
      // FastAPI OAuth2PasswordRequestForm
      // requires application/x-www-form-urlencoded

      const formData = new URLSearchParams();

      formData.append("username", username.trim());
      formData.append("password", password);

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
       * Save access token
       */

      localStorage.setItem(
        "access_token",
        data.access_token
      );

      /*
       * Save refresh token
       */

      if (data.refresh_token) {
        localStorage.setItem(
          "refresh_token",
          data.refresh_token
        );
      }

      /*
       * Save token type
       */

      if (data.token_type) {
        localStorage.setItem(
          "token_type",
          data.token_type
        );
      }

      /*
       * Save complete authentication response
       */

      localStorage.setItem(
        "auth_response",
        JSON.stringify(data)
      );

      /*
       * Notify other frontend components
       * that authentication state changed.
       */

      window.dispatchEvent(
        new Event("auth-change")
      );

      /*
       * Login successful - role ke hisab se bhejein.
       *
       * Role JWT ke andar hota hai. Yahan use sirf raasta chunne ke
       * liye padha jata hai - asli rok backend par lagti hai
       * (require_admin, jo parent ke token par 403 deta hai). Is
       * liye token ki signature yahan jaanchne ki zaroorat nahi.
       */

      const role = readRoleFromToken(data.access_token);

      if (role) {
        localStorage.setItem("role", role);
      }

      window.location.href =
        role === "admin" ? "/admin" : "/dashboard";

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
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("auth_response");
    localStorage.removeItem("role");

    /*
     * Notify navbar/components that the user logged out.
     */

    window.dispatchEvent(
      new Event("auth-change")
    );

    /*
     * Redirect to login.
     */

    window.location.href = "/login";
  };

  return (
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
            Welcome Back.
          </h1>

          <p className="mt-3 text-lg text-text-secondary">
            Sign into your account.
          </p>

          <div className="mt-8 glass p-6">
            <p className="text-sm leading-7 text-text-secondary">
              Continue your voice sessions and access your call history.
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
              Sign in
            </h2>

            <p className="mt-2 text-sm text-text-secondary">
              Enter your credentials to access Vocira.
            </p>

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

              {/* Login button - AuthForm.jsx wale style se match karta hai:
                  glass surface + dono taraf accent glow. Pehle ye
                  bg-accent-secondary (halka cyan) par white text tha,
                  jis ka contrast kamzor tha aur baqi app se mel nahi khata tha. */}
              <motion.button
                type="submit"
                disabled={loading}
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

            {/*
              Self-signup jaan bujh kar nahi hai.

              Parent ka account ERPNext ke Guardian record se juRa
              hota hai (parent_id). Wo ID school banati hai - parent
              na use jaanta hai, na sabit kar sakta hai. Khud banaya
              hua account ya to bekaar hota (koi bachcha nahi milta),
              ya - agar parent_id likhne di jaye - doosre khandaan ka
              data khol deta.

              Is liye account school deti hai. Ye link /signup par
              jata tha jo mojood hi nahi (404).
            */}
            <div className="mt-6 text-center text-sm text-text-secondary">
              Need an account? Please contact the school office.
            </div>

          </div>
        </motion.div>
      </div>
    </div>
  );
}