import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TravelAI — Smart Trip Planner",
  description:
    "Plan your perfect trip with AI-powered itineraries. Get personalized day-by-day travel plans, budget tracking, packing lists, and local tips — all generated in seconds.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-sky-600 focus:text-white focus:rounded-lg focus:outline-none focus:shadow-lg"
        >
          Skip to main content
        </a>
        <div id="main-content" className="flex-1 flex flex-col">
          {children}
        </div>
      </body>
    </html>
  );
}
