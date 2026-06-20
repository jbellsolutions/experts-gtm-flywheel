import "./globals.css";
import type { Metadata } from "next";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "Your brand — Daily Review",
  description: "One hour a day. That's the deal.",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="max-w-3xl mx-auto px-4 pt-4 pb-24">
          <header className="mb-4">
            <h1 className="text-xl font-semibold tracking-tight">Your brand</h1>
            <p className="text-xs text-gray-500">One hour a day. That's the deal.</p>
          </header>
          <Nav />
          <main className="mt-4">{children}</main>
        </div>
      </body>
    </html>
  );
}
