import { NextResponse, type NextRequest } from "next/server";
import { authorizeHostedDemo, hostedDemoEnabled, publicDemoEnabled } from "./lib/hosted-demo";

export function proxy(request: NextRequest) {
  if (!hostedDemoEnabled() || request.nextUrl.pathname === "/api/health") return NextResponse.next();
  const denied = authorizeHostedDemo(request);
  if (denied) return denied;
  // Public access goes only through the aggregate bridge's mock-payment check.
  // Legacy routes and rewrites must not bypass that boundary.
  const path = request.nextUrl.pathname;
  if (publicDemoEnabled() && path.startsWith("/api/") && !path.startsWith("/api/live/")) {
    return Response.json({ detail: "Public demo supports the aggregate workflow only." },
      { status: 403, headers: { "Cache-Control": "no-store" } });
  }
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
