"use client";

/**
 * The admin panel's data, from the backend.
 *
 * This whole section used to run on hardcoded numbers in data.js -
 * 122 lines of fake data and no backend call. The backend endpoints
 * existed, they were simply never wired up.
 *
 * Every admin endpoint sits behind require_admin, so a 403 means
 * "this account is not an admin" - that gets its own message, or the
 * user assumes something is broken.
 */

import { useCallback, useEffect, useState } from "react";

import { authFetch, getAccessToken } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function adminFetch(path, options = {}) {
  if (!API_URL) {
    throw new Error("API URL is not configured (NEXT_PUBLIC_API_URL).");
  }

  if (!getAccessToken()) {
    const error = new Error("Please log in.");
    error.code = "NO_TOKEN";
    throw error;
  }

  // authFetch renews the access token once on a 401 and retries, so a
  // 401 arriving here means the refresh token is gone too - the
  // session really is over.
  const response = await authFetch(path, options);

  if (response.status === 401) {
    const error = new Error("Your session has expired. Please log in again.");
    error.code = "UNAUTHORIZED";
    throw error;
  }

  if (response.status === 403) {
    const error = new Error(
      "This area is for administrators only. Please log in with an admin account."
    );
    error.code = "FORBIDDEN";
    throw error;
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");

    // On responses like 409 the caller needs the real reason, not
    // just "something broke" - something like "Another admin has
    // already joined this call." So both the status and the detail
    // are attached to the error.
    let detail = "";
    try {
      const parsed = JSON.parse(body);
      detail =
        typeof parsed?.detail === "string" ? parsed.detail : "";
    } catch {
      /* the response was not JSON */
    }

    const error = new Error(
      detail ||
        `Server returned HTTP ${response.status}${
          body ? `: ${body.slice(0, 120)}` : ""
        }`
    );
    error.status = response.status;
    error.detail = detail;
    throw error;
  }

  return response.json();
}

/**
 * Data from one endpoint, with loading and error state.
 *
 * One place, rather than rewriting the same useEffect on every
 * page.
 */
export function useAdminData(path, fallback) {
  const [data, setData] = useState(fallback);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setData(await adminFetch(path));
    } catch (err) {
      if (err.code === "NO_TOKEN" || err.code === "UNAUTHORIZED") {
        window.location.href = "/login";
        return;
      }
      setError(err.message || "Could not load data.");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}


/** "2026-09-04T10:32:11" -> "2026-09-04 10:32" */
export function formatTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}


/**
 * File upload.
 *
 * The Content-Type has to be left to the browser here, because a
 * multipart body carries a boundary we do not know. authFetch skips
 * its JSON default when the body is FormData, so this goes through
 * the same renew-on-401 path as every other call.
 */
export async function adminUpload(path, file) {
  if (!API_URL) {
    throw new Error("API URL is not configured (NEXT_PUBLIC_API_URL).");
  }

  if (!getAccessToken()) {
    const error = new Error("Please log in.");
    error.code = "NO_TOKEN";
    throw error;
  }

  const body = new FormData();
  body.append("file", file);

  const response = await authFetch(path, { method: "POST", body });

  if (!response.ok) {
    let detail = `Upload failed (HTTP ${response.status}).`;
    try {
      const parsed = await response.json();
      if (parsed?.detail) {
        detail =
          typeof parsed.detail === "string"
            ? parsed.detail
            : JSON.stringify(parsed.detail);
      }
    } catch {
      /* the body was not JSON */
    }
    throw new Error(detail);
  }

  return response.json();
}
