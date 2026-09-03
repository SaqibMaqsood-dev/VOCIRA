"use client";

import { GradFlow } from "gradflow";
import { useEffect, useState } from "react";

export default function BackgroundGradient() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="pointer-events-none fixed inset-0 -z-20">
      <GradFlow
        config={{
          color1: "#100944",
          color2: "#000000",
          color3: "#100944",
          speed: 0.6,
          scale: 0.8,
          type: "smoke",
          noise: 0.18
        }}
      />
    </div>
  );
}

