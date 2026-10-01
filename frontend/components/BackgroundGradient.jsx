"use client";

import { GradFlow } from "gradflow";
import { Component, useEffect, useRef, useState } from "react";

const CONFIG = {
  color1: "#0a0850",
  color2: "#000000",
  color3: "#0a0850",
  speed: 1,
  scale: 0.8,
  type: "smoke",
  noise: 0.18,
};

// The same colours, still - for a browser that gives no WebGL
const FALLBACK = {
  background:
    "radial-gradient(ellipse at 20% 15%, #0a0850 0%, transparent 60%)," +
    "radial-gradient(ellipse at 80% 85%, #0a0850 0%, transparent 55%), #000000",
};

/**
 * Can this browser hand out a WebGL context right now? It may not: WebGL
 * switched off, an old device, or Chrome blocking it after its GPU process
 * crashed (this machine runs short of memory). GradFlow's renderer (OGL)
 * does not handle that - it logged "unable to create webgl context" and
 * then threw, and the dev overlay covered the page.
 */
function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) return false;
    // only a test - its context is given straight back
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

/** Anything GradFlow still throws ends in the still background, not a broken page. */
class FallBackOnError extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? <div className="h-full w-full" style={FALLBACK} /> : this.props.children;
  }
}

export default function BackgroundGradient() {
  // null until mounted (WebGL is a browser question), then "webgl" or "still"
  const [mode, setMode] = useState(null);
  const box = useRef(null);

  useEffect(() => {
    setMode(webglAvailable() ? "webgl" : "still");
  }, []);

  // The GPU can drop the context later (a driver reset, memory pressure) -
  // the canvas would go black; the still background takes over instead.
  useEffect(() => {
    if (mode !== "webgl") return undefined;
    const canvas = box.current?.querySelector("canvas");
    if (!canvas) return undefined;
    const lost = () => setMode("still");
    canvas.addEventListener("webglcontextlost", lost);
    return () => canvas.removeEventListener("webglcontextlost", lost);
  }, [mode]);

  if (mode === null) return null;

  return (
    <div ref={box} className="pointer-events-none fixed inset-0 -z-20">
      {mode === "webgl" ? (
        <FallBackOnError>
          <GradFlow config={CONFIG} />
        </FallBackOnError>
      ) : (
        <div className="h-full w-full" style={FALLBACK} />
      )}
    </div>
  );
}
