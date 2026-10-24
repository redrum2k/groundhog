import type { Metadata } from "next";
import "./globals.css";

// The invoice workbench keeps its own styles; the run canvas at / has its own.
export const metadata: Metadata = {
  title: "OBJECTION — Job workbench",
  description: "Evidence-led document delivery and simulated order accounting.",
};
export default function JobflowLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
