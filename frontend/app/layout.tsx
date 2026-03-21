import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { GlassNav } from "@/components/GlassNav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AdaptIQ — Employer & employee onboarding",
  description: "JD, team context, and resume — live orchestration stream",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        suppressHydrationWarning
        className={`${geistSans.variable} ${geistMono.variable} relative min-h-screen font-sans antialiased`}
      >
        <div className="relative z-10 flex min-h-screen flex-col">
          <GlassNav />
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
