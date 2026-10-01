"use client";

import { useEffect } from "react";
import FullScreenLoader from "@/components/FullScreenLoader";

// The super admin's panel opens on its schools.
export default function SuperAdminHome() {
  useEffect(() => {
    window.location.replace("/superadmin/schools");
  }, []);

  return <FullScreenLoader label="Opening schools…" subLabel="One moment" />;
}
