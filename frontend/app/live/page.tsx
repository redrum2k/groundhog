"use client";
import { useRouter } from "next/navigation";
import LiveRun from "../../components/run/live-run";
import "../run.css";

// Nikita's intake against the aggregate backend. The canvas demo stays at /.
export default function Page() {
  const router = useRouter();
  return <LiveRun recorded={() => router.push("/")} />;
}
