import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Providers } from "@/components/providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_API_URL?.replace("mirage-api", "mirage-web") ||
  "https://mirage-web-pvgo.onrender.com";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
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
      <body className="min-h-full flex flex-col bg-background font-sans text-foreground">
        <Providers>
          <Navbar />
          <main className="flex-1">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
