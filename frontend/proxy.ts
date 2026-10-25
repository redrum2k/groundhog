import { NextResponse, type NextRequest } from "next/server";
import { authorizeHostedDemo, hostedDemoEnabled } from "./lib/hosted-demo";

export function proxy(request: NextRequest) {
  if (!hostedDemoEnabled() || request.nextUrl.pathname === "/api/health") return NextResponse.next();
  const denied = authorizeHostedDemo(request);
  if (denied) return denied;
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
