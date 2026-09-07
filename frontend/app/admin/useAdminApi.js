"use client";

/**
 * Admin panel ka data backend se.
 *
 * Pehle ye poora hissa data.js ke hardcoded numbers par chalta tha -
 * 122 lines jhoota data, koi backend call nahi. Backend ke endpoints
 * mojood thay, bas wire nahi thay.
 *
 * Saare admin endpoints require_admin ke peeche hain, is liye 403 ka
 * matlab hai "ye account admin nahi" - us ke liye alag paighaam hai,
 * warna user samajhta hai kuch toot gaya.
 */

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function adminFetch(path, options = {}) {
  if (!API_URL) {
    throw new Error("API URL is not configured (NEXT_PUBLIC_API_URL).");
  }

  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null;

  if (!token) {
    const error = new Error("Please log in.");
    error.code = "NO_TOKEN";
    throw error;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

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
    throw new Error(
      `Server returned HTTP ${response.status}${body ? `: ${body.slice(0, 120)}` : ""}`
    );
  }

  return response.json();
}

/**
 * Ek endpoint se data, loading aur error ke sath.
 *
 * Har page mein wahi useEffect dobara likhne ke bajaye ek jagah.
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
