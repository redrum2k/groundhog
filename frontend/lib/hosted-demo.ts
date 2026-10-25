import { createHash, timingSafeEqual } from "node:crypto";

export const publicDemoEnabled = () => process.env.BROKER_PUBLIC_DEMO === "1";
export const hostedDemoEnabled = () => process.env.BROKER_HOSTED_DEMO === "1" || publicDemoEnabled();

// Shared operator access for a hosted demo, not customer/tenant authentication.
// Check again in the live route handler so it does not depend on Proxy alone.
export function authorizeHostedDemo(request: Request): Response | null {
  const fail = (status: number, detail: string, headers = {}) =>
    Response.json({ detail }, { status, headers: { "Cache-Control": "no-store", ...headers } });
  const username = process.env.DEMO_USERNAME;
  const password = process.env.DEMO_PASSWORD;
  let origin: URL;
  try {
    origin = new URL(process.env.APP_ORIGIN ?? "");
    if (origin.protocol !== "https:" || origin.origin !== process.env.APP_ORIGIN) throw new Error();
  } catch {
    return fail(503, "Set APP_ORIGIN to the exact public HTTPS origin, without a trailing slash.");
  }
  if (!publicDemoEnabled() && (!username || username.includes(":") || !password || password.length < 20 ||
      [process.env.INTERNAL_API_TOKEN, process.env.REVIEWER_API_TOKEN].includes(password))) {
    return fail(503, "Configure a demo username and a separate password of at least 20 characters.");
  }
  const url = new URL(request.url);
  if ((request.headers.get("host") ?? url.host) !== origin.host) {
    return fail(403, "Unrecognized demo host.");
  }
  if ((request.headers.get("x-forwarded-proto") ?? url.protocol.slice(0, -1)) !== "https") {
    return fail(403, "Hosted demo requires HTTPS.");
  }
  const expected = `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
  const digest = (value: string) => createHash("sha256").update(value).digest();
  if (!publicDemoEnabled() && !timingSafeEqual(digest(request.headers.get("authorization") ?? ""), digest(expected))) {
    return fail(401, "Demo sign-in required.", { "WWW-Authenticate": 'Basic realm="Groundhog demo", charset="UTF-8"' });
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method) && request.headers.get("origin") !== origin.origin) {
    return fail(403, "Same-origin demo command required.");
  }
  return null;
}
