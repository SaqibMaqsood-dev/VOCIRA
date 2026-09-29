"use client";

import { useEffect, useRef } from "react";

/*
 * Live captions of the caller's own speech, word by word as they talk.
 *
 * Whisper only returns text once a sentence is over, so on its own the
 * caller saw nothing while speaking. The browser's speech recognition
 * gives interim words as they are said; Whisper's text - what the
 * assistant actually acts on - replaces them once it arrives.
 *
 * Chrome and Edge on a computer only. On phones the browser's
 * recognizer can take the microphone away from the call itself, which
 * would silence the caller to the assistant - far worse than no
 * captions. Note the browser sends this audio to its own speech
 * service (Google for Chrome).
 */

const SPEECH_LANG = { ur: "ur-PK", en: "en-US" };

// The backend ignores the mic for 0.6s after the agent's audio ends;
// waiting a little longer keeps the tail of its voice, coming back out
// of the speakers, from being captioned as the caller's.
const RESUME_AFTER_AGENT_MS = 700;

const FATAL_ERRORS = new Set([
  "not-allowed",
  "service-not-allowed",
  "language-not-supported",
]);

function recognitionClass() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function isMobileDevice() {
  if (typeof navigator === "undefined") return false;
  if (navigator.userAgentData?.mobile) return true;
  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) return true;
  // iPadOS reports itself as a Mac.
  return /Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1;
}

export function liveCaptionsSupported() {
  return Boolean(recognitionClass()) && !isMobileDevice();
}

/**
 * enabled        the call is up and the caller's mic is live
 * language       "ur" | "en" - the call's language, as Whisper uses it
 * agentSpeaking  true while the agent talks (and before it has greeted)
 * onText(text)   the caller's current sentence so far
 *
 * Returns { reset }: call it once Whisper's text for the sentence has
 * arrived, so the next sentence starts from nothing.
 */
export function useLiveCaptions({ enabled, language, agentSpeaking, onText }) {
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const recognitionRef = useRef(null);
  const disabledRef = useRef(false);
  const api = useRef({
    reset: () => recognitionRef.current?.abort(),
  });

  useEffect(() => {
    const Recognition = recognitionClass();

    if (
      !enabled ||
      agentSpeaking ||
      !Recognition ||
      isMobileDevice() ||
      disabledRef.current
    ) {
      return;
    }

    let stopped = false;
    let restartTimer = null;

    const start = () => {
      if (stopped || recognitionRef.current) return;

      const recognition = new Recognition();
      recognition.lang = SPEECH_LANG[language] || SPEECH_LANG.ur;
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onresult = (event) => {
        let text = "";
        for (let i = 0; i < event.results.length; i++) {
          text += event.results[i][0].transcript;
        }
        text = text.trim();
        if (text) onTextRef.current?.(text);
      };

      recognition.onerror = (event) => {
        if (FATAL_ERRORS.has(event.error)) {
          disabledRef.current = true;
          stopped = true;
        }
      };

      // Chrome ends a session after a stretch of silence, and reset()
      // aborts one on purpose - either way, listen again.
      recognition.onend = () => {
        if (recognitionRef.current === recognition) {
          recognitionRef.current = null;
        }
        if (!stopped) restartTimer = setTimeout(start, 250);
      };

      recognitionRef.current = recognition;

      try {
        recognition.start();
      } catch {
        recognitionRef.current = null;
      }
    };

    const firstStart = setTimeout(start, RESUME_AFTER_AGENT_MS);

    return () => {
      stopped = true;
      clearTimeout(firstStart);
      clearTimeout(restartTimer);
      const recognition = recognitionRef.current;
      recognitionRef.current = null;
      recognition?.abort();
    };
  }, [enabled, language, agentSpeaking]);

  return api.current;
}
