import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}>
      <body className={`${GeistSans.className} min-h-full flex flex-col bg-background text-foreground`}>
        {children}
      </body>
    </html>
  );
}
