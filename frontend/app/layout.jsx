import { Roboto, Poppins } from "next/font/google";
import "./globals.css";
import AppChrome from "./AppChrome";

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
    "Vocira AI assistant helps students and parents get school information instantly."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${roboto.variable} ${poppins.variable}`}>
      <body className="flex min-h-screen flex-col">
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
