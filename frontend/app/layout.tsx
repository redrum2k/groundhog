import type { Metadata } from "next";
import { S } from "../lib/run/scenario";

export const metadata: Metadata = {
  title: "Groundhog run",
  description: `${S.seat}.`,
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
