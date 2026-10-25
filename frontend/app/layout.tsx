import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Groundhog run",
  description: "Order-to-cash agent for a data broker.",
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
