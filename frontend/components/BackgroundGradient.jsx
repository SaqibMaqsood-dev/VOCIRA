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

// While WebGL is away, look for it again this often - the GPU can come
// back (a driver reset, memory freed) and GradFlow with it, no reload.
const RETRY_MS = 15000;

const GLOW = { background: "radial-gradient(circle, #0a0850 0%, transparent 65%)" };

/** The same colours for a browser that gives no WebGL - drifting slowly (globals.css). */
function CssGradient() {
  return (
    <div className="relative h-full w-full overflow-hidden bg-black">
      <div className="gradient-drift absolute -left-[25vmax] -top-[25vmax] h-[80vmax] w-[80vmax] rounded-full" style={GLOW} />
      <div
        className="gradient-drift gradient-drift-reverse absolute -bottom-[25vmax] -right-[25vmax] h-[75vmax] w-[75vmax] rounded-full"
        style={GLOW}
      />
    </div>
  );
}

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

/** Anything GradFlow still throws ends in the CSS background, not a broken page. */
class FallBackOnError extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    this.props.onFail?.();
  }

  render() {
    return this.state.failed ? <CssGradient /> : this.props.children;
  }
}

export default function BackgroundGradient() {
  // null until mounted (WebGL is a browser question), then "webgl" or "css"
  const [mode, setMode] = useState(null);
  // a fresh GradFlow each time WebGL comes back - the old one's context is gone
  const [round, setRound] = useState(0);
  const box = useRef(null);

  useEffect(() => {
    setMode(webglAvailable() ? "webgl" : "css");
  }, []);

  // The GPU can drop the context later (a driver reset, memory pressure) -
  // the canvas would go black; the CSS background takes over instead.
  // GradFlow's canvas comes a moment after this mounts, so it is watched
  // on the box (the event does not bubble - caught on the way down).
  useEffect(() => {
    if (mode !== "webgl") return undefined;
    const holder = box.current;
    if (!holder) return undefined;
    const lost = () => setMode("css");
    holder.addEventListener("webglcontextlost", lost, true);
    return () => holder.removeEventListener("webglcontextlost", lost, true);
  }, [mode, round]);

  // Without WebGL, keep asking - when the tab is looked at again, and now
  // and then - and bring GradFlow back once the browser has it again.
  useEffect(() => {
    if (mode !== "css") return undefined;
    const retry = () => {
      if (document.visibilityState !== "visible" || !webglAvailable()) return;
      setRound((n) => n + 1);
      setMode("webgl");
    };
    const timer = setInterval(retry, RETRY_MS);
    document.addEventListener("visibilitychange", retry);
    window.addEventListener("focus", retry);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", retry);
      window.removeEventListener("focus", retry);
    };
  }, [mode]);

  if (mode === null) return null;

  return (
    <div ref={box} className="pointer-events-none fixed inset-0 -z-20">
      {mode === "webgl" ? (
        <FallBackOnError key={round} onFail={() => setMode("css")}>
          <GradFlow config={CONFIG} />
        </FallBackOnError>
      ) : (
        <CssGradient />
      )}
    </div>
  );
}
