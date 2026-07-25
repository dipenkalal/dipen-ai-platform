import type {
  Metadata,
} from "next";

import "./globals.css";

import AppNavigation from "./components/AppNavigation";


export const metadata: Metadata = {
  title: {
    default: "Dipen AI Platform",
    template: "%s | Dipen AI Platform",
  },
  description:
    "Local AI agents, knowledge management, execution history and analytics.",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-white antialiased">
        <AppNavigation />

        {children}
      </body>
    </html>
  );
}
