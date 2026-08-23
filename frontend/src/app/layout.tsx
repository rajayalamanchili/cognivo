import type { Metadata } from "next";
import { Baloo_2, Nunito } from "next/font/google";
import DemoBadge from "@/components/DemoBadge";
import Nav from "@/components/Nav";
import "./globals.css";

// Kid-friendly type pairing: Baloo 2 (bold, rounded-lg) for headings,
// Nunito (rounded-lg but highly legible at body-text sizes) for everything
// else -- wired into globals.css's `--font-heading`/`--font-sans`.
const baloo = Baloo_2({
  variable: "--font-baloo",
  subsets: ["latin"],
});

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Cognivo",
  description: "A domain-agnostic learning platform that adapts to how you learn.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${baloo.variable} ${nunito.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <DemoBadge />
        <Nav />
        {children}
      </body>
    </html>
  );
}
