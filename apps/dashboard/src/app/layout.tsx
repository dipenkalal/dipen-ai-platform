import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dipen AI Platform",
  description: "Private Local First AI Operating Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}