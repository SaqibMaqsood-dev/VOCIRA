"use client";

/**
 * The session: tokens, renewal, and authenticated fetch.
 *
 * The access token lives for ACCESS_TOKEN_EXPIRE_MINUTES (15 by
 * default). Before this module existed, nothing ever renewed it: the
 * refresh token was saved at login and only ever deleted at logout,
 * and no code path called /auth/refresh. So every session ended
 * fifteen minutes in, with a 401 the user read as "it broke".
 *
 * authFetch() closes that gap. On a 401 it renews once, retries the
 * request, and only then gives up.
 *
 * WHY ONE IN-FLIGHT REFRESH
 *
 * A page can easily fire several requests at once (the dashboard
 * loads stats, sessions and escalations together). If each one
 * renewed on its own, they would race: the backend revokes the old
 * refresh token as it issues a new one, so the first to land
 * invalidates the token the others are still holding, and they would
 * all fail. The pending promise is shared, so a burst of 401s
 * produces exactly one renewal.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";
const TOKEN_TYPE_KEY = "token_type";

// localStorage throws in some privacy modes rather than returning
// null, so every access is guarded.
function read(key) {
  try {
    return typeof window === "undefined"
      ? null
      : localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (typeof window !== "undefined") {
      localStorage.setItem(key, value);
    }
  } catch {
    /* a session that cannot be remembered still works for this tab */
  }
}

function drop(key) {
  try {
    if (typeof window !== "undefined") {
      localStorage.removeItem(key);
    }
  } catch {
    /* nothing to do */
  }
}

export function getAccessToken() {
  return read(ACCESS_KEY);
}

export function getRefreshToken() {
  return read(REFRESH_KEY);
}

/**
 * Store what /login or /refresh returned.
 *
 * The backend now returns a refresh token from both. It returned one
 * from neither before, which is why nothing could be renewed.
 */
export function saveSession(data) {
  if (data?.access_token) {
    write(ACCESS_KEY, data.access_token);
  }

  if (data?.refresh_token) {
    write(REFRESH_KEY, data.refresh_token);
  }

  if (data?.token_type) {
    write(TOKEN_TYPE_KEY, data.token_type);
  }
}

export function clearSession() {
  drop(ACCESS_KEY);
  drop(REFRESH_KEY);
  drop(TOKEN_TYPE_KEY);
  drop("role");

  // Login used to write the entire response here as well. Nothing
  // ever read it, and it left a second copy of the refresh token in
  // localStorage - so it is no longer written, but anyone with an
  // older session still has one to clear.
  drop("auth_response");
}

// The renewal currently in flight, shared by every caller.
let pending = null;

/**
 * Exchange the refresh token for a new pair.
 *
 * Returns the new access token, or null if the session is over.
 */
export function refreshSession() {
  if (pending) {
    return pending;
  }

  const refreshToken = getRefreshToken();

  if (!refreshToken || !API_URL) {
    return Promise.resolve(null);
  }

  pending = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshtoken: refreshToken }),
      });

      if (!response.ok) {
        // The refresh token is expired, revoked, or belongs to an
        // account that no longer exists. There is nothing left to
        // retry with.
        clearSession();
        return null;
      }

      const data = await response.json();
      saveSession(data);
      return data?.access_token ?? null;
    } catch {
      // A network failure is not an expired session - keep the
      // tokens so the next attempt can still use them.
      return null;
    } finally {
      pending = null;
    }
  })();

  return pending;
}

/**
 * fetch() with the bearer token attached, renewing once on a 401.
 *
 * Returns the Response untouched: callers already read status codes
 * (403 for non-admins, 409 for a claimed call), so this must not
 * swallow them.
 */
export async function authFetch(path, options = {}) {
  if (!API_URL) {
    throw new Error("API URL is not configured (NEXT_PUBLIC_API_URL).");
  }

  const url = path.startsWith("http") ? path : `${API_URL}${path}`;

  const send = (token) => {
    const headers = { ...(options.headers || {}) };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    // FormData carries its own multipart boundary, so Content-Type
    // has to be left for the browser to set.
    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    return fetch(url, { ...options, headers });
  };

  let response = await send(getAccessToken());

  if (response.status !== 401) {
    return response;
  }

  const renewed = await refreshSession();

  if (!renewed) {
    return response;
  }

  return send(renewed);
}
