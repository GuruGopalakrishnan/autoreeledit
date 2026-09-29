import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { montserrat, anton } from "@/lib/fonts";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "autoreel",
  description: "AI-powered auto-editor for talking-head videos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${montserrat.variable} ${anton.variable} dark h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#0b0b0f] text-[#f2f2f5]">{children}</body>
    </html>
  );
}
