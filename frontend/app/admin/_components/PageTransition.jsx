"use client";

/**
 * How admin pages come and go: at once.
 *
 * Each page used to arrive with a fade (opacity 0 -> 1 over 0.45s, and a
 * 6px rise). Going from page to page, the whole content area dimmed and
 * came back every time - it read as the panel flickering, not as a
 * transition. The sidebar and header never move, so the content simply
 * changing in place is what feels steady.
 *
 * A page still loading its data shows the loader in this same area
 * (FullScreenLoader, inside AdminLayout's LoaderInFrame) - and only when
 * the data takes long enough to need one.
 */

export default function PageTransition({ children }) {
  return children;
}
