import { Roboto, Poppins } from "next/font/google";
import "./globals.css";
import AppChrome from "./AppChrome";
import InstallPrompt from "@/components/InstallPrompt";
import ServiceWorker from "@/components/ServiceWorker";

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-heading"
});

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-body"
});

export const metadata = {
  title: "Vocira – AI Powered Voice Agent System",
  description:
    "Vocira AI assistant helps students and parents get school information instantly.",

  // Next builds /manifest.webmanifest from manifest.js itself
  manifest: "/manifest.webmanifest",

  appleWebApp: {
    capable: true,
    title: "Vocira",
    // With "default", iOS adds a white bar that looks wrong against
    // the dark theme
    statusBarStyle: "black-translucent",
  },

  other: {
    // `capable: true` above emits the standardised
    // "mobile-web-app-capable". Safari only started honouring that
    // name in iOS 15.4; before then it read the apple- prefixed one,
    // and without it an older iPhone opens the installed app in a
    // Safari chrome instead of standalone. Next does not emit the
    // deprecated name itself, so it is declared here.
    "apple-mobile-web-app-capable": "yes",
  },

  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/icons/apple-touch-icon.png",
  },
};

// In Next 15+ themeColor moved out of metadata and into viewport
export const viewport = {
  themeColor: "#05041c",
  width: "device-width",
  initialScale: 1,
  // In the installed app, let the background run under the notch
  viewportFit: "cover",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${roboto.variable} ${poppins.variable}`}>
      <body className="flex min-h-screen flex-col">
        <AppChrome>{children}</AppChrome>
        <InstallPrompt />
        <ServiceWorker />
      </body>
    </html>
  );
}
