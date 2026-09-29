"use client";

import { useEffect, useRef } from "react";

/**
 * The conversation as text, while the call runs.
 *
 * lines: [{ id, role: "user" | "agent", text, live?, final? }]
 *
 *   live   the caller is still talking - the browser's interim words,
 *          shown faded until Whisper's text replaces them
 *   final  false while the agent is still saying the line; its words
 *          arrive one at a time, in step with the voice
 *
 * dir="auto" lets an Urdu line run right-to-left and an English one
 * left-to-right in the same list.
 */
export default function CallTranscript({ lines }) {
  const scroller = useRef(null);

  useEffect(() => {
    const box = scroller.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [lines]);

  return (
    <div
      ref={scroller}
      aria-live="polite"
      aria-label="Conversation transcript"
      className="mx-auto mt-4 max-h-36 w-full max-w-md space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-white/5 p-3 text-start backdrop-blur-md [scrollbar-color:rgba(255,255,255,0.25)_transparent] [scrollbar-width:thin] sm:max-h-48"
    >
      {lines.length === 0 ? (
        <p className="py-2 text-center text-xs text-text-secondary/70">
          What you say will appear here.
        </p>
      ) : (
        lines.map((line) => {
          const isUser = line.role === "user";

          return (
            <div
              key={line.id}
              className={`flex flex-col ${
                isUser ? "items-end" : "items-start"
              }`}
            >
              <span className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-text-secondary/70">
                {isUser ? "You" : "Vocira"}
              </span>

              <p
                dir="auto"
                // text-start, not text-left: with dir="auto" an Urdu
                // line then runs from the right edge, and its words
                // appear right-to-left as they are spoken.
                className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3 py-1.5 text-start text-sm leading-relaxed ${
                  isUser
                    ? "rounded-br-sm bg-accent-primary/25"
                    : "rounded-bl-sm bg-white/10"
                } ${
                  line.live
                    ? "italic text-text-secondary"
                    : "text-text-primary"
                }`}
              >
                {line.text}
                {(line.live || line.final === false) && (
                  <span
                    aria-hidden="true"
                    className="ms-0.5 inline-block animate-pulse text-text-secondary"
                  >
                    ▍
                  </span>
                )}
              </p>
            </div>
          );
        })
      )}
    </div>
  );
}
