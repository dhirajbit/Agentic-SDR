import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist_Mono } from "next/font/google";

import "./globals.css";

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Agentic SDR — Operator Console",
  description: "Multi-tenant control panel for the Agentic SDR.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={geistMono.variable}>{children}</body>
      </html>
    </ClerkProvider>
  );
}
