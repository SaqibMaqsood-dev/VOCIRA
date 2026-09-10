/**
 * PWA manifest.
 *
 * Next serves this at /manifest.webmanifest by itself, so there is
 * no need for a separate file in public/.
 *
 * start_url is "/assistant", not "/": someone who installs the app
 * on their phone comes to talk, not to read the marketing page. The
 * home page still opens in the browser.
 */

export default function manifest() {
  return {
    name: "Vocira – School Voice Assistant",
    short_name: "Vocira",
    description:
      "Ask about your child's attendance, results, fees and timetable — just by speaking.",

    start_url: "/assistant",
    scope: "/",
    display: "standalone",
    orientation: "portrait",

    background_color: "#05041c",
    theme_color: "#05041c",

    categories: ["education", "productivity"],
    lang: "en",
    dir: "ltr",

    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      // Android crops the icon into a circle/squircle. The logo is
      // kept small and centred in the maskable icons, or the edges
      // get cut off.
      {
        src: "/icons/maskable-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icons/maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],

    shortcuts: [
      {
        name: "Start a call",
        short_name: "Call",
        url: "/assistant",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
      {
        name: "My calls",
        short_name: "Calls",
        url: "/dashboard",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
    ],
  };
}
