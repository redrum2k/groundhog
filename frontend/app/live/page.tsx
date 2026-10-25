"use client";
import { useRouter } from "next/navigation";
import LiveRun from "../../components/run/live-run";
import "../run.css";

// Both primary entry points use the funded aggregate backend.
export default function Page() {
  const router = useRouter();
  return <LiveRun recorded={() => router.push("/demo")} />;
}
