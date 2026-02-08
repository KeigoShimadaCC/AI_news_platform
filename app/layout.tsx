import type { Metadata } from "next";
import { Providers } from "@/lib/providers";
import { Navigation } from "@/components/Navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI News Platform",
  description: "Your daily AI news digest - news, tips, and papers curated from top sources",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen">
            <Navigation />
            <div className="mx-auto max-w-6xl px-4 py-6">{children}</div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
