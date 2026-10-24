import { NextRequest } from "next/server";

// A narrow same-origin bridge, not a general URL proxy. Privileged capabilities
// stay here and are available only in the explicitly enabled localhost demo.
const id = "[A-Za-z0-9_-]+";
const publicRoutes = [
  ["GET", /^corpora$/], ["GET", /^runs$/],
  ["GET", new RegExp(`^runs/${id}/events$`)],
  ["GET", new RegExp(`^improvements/scopes/${id}$`)],
  ["POST", /^requests$/], ["GET", new RegExp(`^requests/${id}$`)],
  ["POST", new RegExp(`^requests/${id}/(answers|quotes)$`)],
  ["POST", /^quote-acceptance$/], ["GET", new RegExp(`^orders/${id}$`)],
  ["GET", new RegExp(`^orders/${id}/(payment|artifacts/${id})$`)],
  ["POST", new RegExp(`^orders/${id}/(acceptance|disputes|answers|amendments|approvals|funding-preparation|funding-authorizations)$`)],
] as const;
const workerRoutes = new RegExp(`^worker/(requests/${id}/compile|orders/${id}/(work|retry|offers|approvals)|payments/work|improvements/(commands|orders/${id}/observe))$`);
const reviewerRoutes = new RegExp(`^reviewer/(orders/${id}/decisions|improvements/review)$`);

function localOrigin(request: NextRequest) {
  const url = new URL(request.url);
  // Next normalizes request.url to localhost even when the browser uses 127.0.0.1.
  // Validate the actual Host and Origin, never a forwarded host supplied by a client.
  const host = request.headers.get("host");
  if (!host || !/^(localhost|127\.0\.0\.1|\[::1\])(?::[0-9]+)?$/.test(host)) return false;
  const origin = request.headers.get("origin");
  return origin === `${url.protocol}//${host}` && request.headers.get("sec-fetch-site") !== "cross-site";
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  const worker = request.method === "POST" && workerRoutes.test(path);
  const reviewer = request.method === "POST" && reviewerRoutes.test(path);
  const ordinary = publicRoutes.some(([method, pattern]) => method === request.method && pattern.test(path));
  if (!ordinary && !worker && !reviewer) return Response.json({ detail: "Unsupported catalog route" }, { status: 404 });
  if (request.method !== "GET" && !localOrigin(request)) return Response.json({ detail: "Local same-origin command required" }, { status: 403 });
  const headers = new Headers();
  if (worker || reviewer) {
    if (process.env.ENABLE_CATALOG_DEMO_CONTROLS !== "true") return Response.json({ detail: "Synthetic staff controls are disabled" }, { status: 403 });
    const token = worker ? process.env.INTERNAL_API_TOKEN : process.env.REVIEWER_API_TOKEN;
    if (!token) return Response.json({ detail: "Server-side role capability is not configured" }, { status: 503 });
    headers.set(worker ? "X-Internal-Token" : "X-Reviewer-Token", token);
  }
  let upstream = path.startsWith("runs") ? `api/runs${path === "runs" ? "/" : path.slice(4)}` : path;
  if (worker) upstream = path.replace(/^worker\//, "internal/");
  if (/^(worker\/|reviewer\/)?improvements\//.test(path)) upstream = path.replace(/^(worker\/|reviewer\/)?improvements\//, "api/catalog-improvements/");
  let body: string | undefined;
  if (request.method === "POST") {
    body = await request.text();
    if (Buffer.byteLength(body) > 3_000_000) return Response.json({ detail: "Request too large" }, { status: 413 });
    headers.set("Content-Type", "application/json");
  }
  const backend = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  try {
    const response = await fetch(`${backend}/${upstream}${request.nextUrl.search}`, {
      method: request.method, headers, body, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(75_000),
    });
    return new Response(response.body, { status: response.status, headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    } });
  } catch {
    return Response.json({ detail: "Catalog backend unavailable; retry with the same command key" }, { status: 502 });
  }
}
export const GET = forward;
export const POST = forward;
