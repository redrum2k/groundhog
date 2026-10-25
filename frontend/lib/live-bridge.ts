// Server-only local demo boundary. These routes deliberately have no public-host mode.
export async function bridge(request: Request, path: string[]) {
  const fail = (status: number, detail: string) => Response.json({detail}, {status, headers: {"Cache-Control":"no-store"}});
  let url: URL, requestOrigin: URL, backend: URL;
  try {
    url = new URL(request.url);
    requestOrigin = new URL(`${url.protocol}//${request.headers.get("host") ?? url.host}`);
    backend = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
  } catch { return fail(400, "Invalid local bridge address."); }
  const loopback = (host: string) => host === "127.0.0.1" || host === "localhost" || host === "[::1]";
  if (process.env.BROKER_LOCAL_DEMO !== "1" || !loopback(url.hostname) || !loopback(requestOrigin.hostname) || !loopback(backend.hostname) || backend.protocol !== "http:") return fail(403, "Broker bridge requires trusted loopback local-demo mode.");
  if (request.method !== "GET" && request.headers.get("origin") !== requestOrigin.origin) return fail(403, "Same-origin local-demo command required.");
  const internal = process.env.INTERNAL_API_TOKEN;
  const reviewer = process.env.REVIEWER_API_TOKEN;
  if (!internal || !reviewer || internal === reviewer) return fail(503, "Distinct server-side worker and reviewer credentials are required.");
  if (path.some(p => !/^[a-zA-Z0-9_:.-]+$/.test(p) || p === "." || p === "..")) return fail(404, "Operation not supported.");
  const target = "/" + path.join("/");
  const id = "[a-zA-Z0-9_:.-]+";
  const get = new RegExp(`^/(source-learning/state|runs/${id}/(events|evidence/${id})|orders/${id}/artifacts/${id})$`);
  const post = new RegExp(`^/(source-learning/(sources|resolve|propose|qualify|approve|activate|revoke)|runs|runs/${id}/(decisions|offers|answers)|requests/${id}/(answers|quotes)|internal/requests/${id}/compile|quote-acceptance|orders/${id}/(funding-preparation|funding-authorizations|acceptance|disputes))$`);
  if (!(request.method === "GET" ? get.test(target) : request.method === "POST" && post.test(target))) return fail(404, "Operation not supported.");
  const headers = new Headers({"Content-Type":"application/json"});
  const key = request.headers.get("idempotency-key");
  if (key) headers.set("Idempotency-Key", key);
  if (target.endsWith("/decisions")) headers.set("X-Reviewer-Token", reviewer);
  if (target.startsWith("/internal/") || target.endsWith("/offers")) headers.set("X-Internal-Token", internal);
  if (target.startsWith("/source-learning/")) {
    if (target.endsWith("/resolve")) {
      const owner = process.env.SOURCE_OWNER_API_TOKEN;
      if (!owner || owner === internal || owner === reviewer) return fail(503, "Distinct simulated source-owner credential required.");
      headers.set("X-Source-Owner-Token", owner);
    } else if (/\/(qualify|approve|activate|revoke)$/.test(target)) headers.set("X-Reviewer-Token", reviewer);
    else headers.set("X-Internal-Token", internal);
  }
  const query = new URLSearchParams();
  if (target.endsWith("/events")) for (const k of ["after", "limit"]) if (url.searchParams.has(k)) query.set(k, url.searchParams.get(k)!);
  try {
    const response = await fetch(new URL(target + (query.size ? "?" + query : ""), backend), {
      method: request.method, headers, body: request.method === "POST" ? await request.text() : undefined, cache: "no-store", redirect: "error",
    });
    return new Response(await response.arrayBuffer(), {status: response.status, headers: {"Content-Type": response.headers.get("Content-Type") ?? "application/json", "Cache-Control":"no-store"}});
  } catch { return fail(502, "Backend unavailable; no recorded fallback was substituted."); }
}
