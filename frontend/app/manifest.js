/**
 * PWA manifest.
 *
 * Next ise khud /manifest.webmanifest par serve karta hai, is liye
 * public/ mein alag file rakhne ki zaroorat nahi.
 *
 * start_url "/assistant" hai, "/" nahi: jo banda app ko phone par
 * install karta hai wo baat karne aata hai, marketing page parhne
 * nahi. Home page browser mein khulta rehta hai.
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
      // Android icon ko gol/squircle mein kaat-ta hai. Maskable icons
      // mein logo beech mein chhota rakha gaya hai, warna kinare kat
      // jate hain.
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
