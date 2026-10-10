import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://mirage-web.onrender.com"),
  title: "Mirage — The Scam Vaccine",
  description:
    "Don't detect scams. Vaccinate people against them. Fire drills, a live call guardian, and a scammer honeypot.",
  openGraph: {
    title: "Mirage — The Scam Vaccine",
    description:
      "Don't detect scams. Vaccinate people against them. Fire drills, a live call guardian, and a scammer honeypot.",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Mirage — The Scam Vaccine",
    description:
      "Don't detect scams. Vaccinate people against them. Fire drills, a live call guardian, and a scammer honeypot.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Navbar />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
