/**
 * A small vocabulary for handing a call to a person (handoff).
 *
 * Two places need it - the assistant page has to display the state,
 * and the visualizer has to know whose audio the waveform should
 * follow. Written separately in both places, one would change and
 * the other would be left behind.
 */

/**
 * The AI sets this attribute on its own participant:
 *
 *     requested  -> an admin has been called
 *     connected  -> the admin has joined, the AI is leaving
 *     no_answer  -> nobody picked up, the AI is taking over again
 */
export const HANDOFF_ATTRIBUTE = "vocira.handoff";

/**
 * Is this participant an admin?
 *
 * Identity is the first and strongest source (`admin-<id>` is built
 * by the backend). Metadata is the second - it carries both role and
 * type.
 */
export function isAdminParticipant(participant) {
  if (String(participant?.identity || "").startsWith("admin-")) {
    return true;
  }

  try {
    const meta = JSON.parse(participant?.metadata || "{}");
    return meta.role === "admin" || meta.type === "admin";
  } catch {
    return false;
  }
}
