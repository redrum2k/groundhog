import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OBJECTION — Job workbench",
  description: "Evidence-led document delivery and simulated order accounting.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
