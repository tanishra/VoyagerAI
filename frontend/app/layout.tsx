import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "VoyagerAI — Smart Trip Planner",
  description:
    "Plan your perfect trip with AI-powered itineraries. Get personalized day-by-day travel plans, budget tracking, packing lists, and local tips — all generated in seconds.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "VoyagerAI",
  },
  icons: {
    icon: "/icon-192.png",
    apple: "/icon-192.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#b04a3a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}>
      <body className={`${GeistSans.className} min-h-full flex flex-col bg-background text-foreground`}>
        {/* impeccable:direction-contract
          THESIS: The travel magazine spread as a living interface — warm white paper, hairline typography, destination photography choreographed across the gutter, where the gutter becomes the conversation seam between user and agent. Refuses the SaaS template of centered hero + feature cards.
          OWN-WORLD: Warm white paper ground (#f7f3ed), charcoal ink (#2a2520), cinnabar red accent (#c44536), terracotta warmth, sage secondary. Hairline rules as structural dividers. Didot-style display contrast at large sizes, precise sans body. Generous negative space, rigid grid for data.
          STORY: A visitor opens to a magazine spread — destination photography on one side, the product name in elegant hairlines on the other, a warm red rule between them. They understand this is a premium AI travel planner, not a form wizard. They click through to chat.
          FIRST VIEWPORT: Full-bleed destination photo left, product name in display serif right, cinnabar hairline rule as the seam, CTA as a small ranked caption beneath the headline. No aurora, no blur, no gradient text.
          FORM: Brodovitch Bazaar Spread, position 1 of 7, seed key 0b5ac004.
          FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
        */}
        {children}
      </body>
    </html>
  );
}
