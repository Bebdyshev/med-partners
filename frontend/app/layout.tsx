import type { Metadata } from "next";
import { Spectral, Commissioner, IBM_Plex_Mono } from "next/font/google";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

// All three carry Cyrillic — the UI is Russian. Distinct editorial pairing.
const display = Spectral({ subsets: ["latin", "cyrillic"], weight: ["500", "600"], variable: "--font-display" });
const body = Commissioner({ subsets: ["latin", "cyrillic"], weight: ["400", "500", "600"], variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin", "cyrillic"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "MedArchive — реестр услуг и цен",
  description: "Единая база услуг и цен клиник-партнёров",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <div className="app">
          <Sidebar />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
