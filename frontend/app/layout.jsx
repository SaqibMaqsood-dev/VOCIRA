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

  // Next manifest.js se /manifest.webmanifest khud banata hai
  manifest: "/manifest.webmanifest",

  appleWebApp: {
    capable: true,
    title: "Vocira",
    // "default" par iOS safaid patti daal deta hai jo gehre theme par
    // bhaddi lagti hai
    statusBarStyle: "black-translucent",
  },

  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/icons/apple-touch-icon.png",
  },
};

// Next 15+ mein themeColor metadata se nikal kar viewport mein aa gaya
export const viewport = {
  themeColor: "#05041c",
  width: "device-width",
  initialScale: 1,
  // Install ki hui app mein notch ke neeche tak background jaye
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
