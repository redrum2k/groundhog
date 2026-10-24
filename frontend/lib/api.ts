import type {
  Actor,
  Command,
  DocumentUpload,
  InvestigationRequest,
  OrderCreate,
  OrderView,
} from "./jobflow.generated";

export const API = "/api/jobflow";
export type Session = { token: string; actor: Actor };
export type CommandInput = Omit<
  Command,
  "idempotency_key" | "expected_revision"
>;
export type PreparedMutation = Readonly<{
  path: string;
  body: string;
  label: string;
}>;
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  token?: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const value = await response.json();
      detail =
        typeof value.detail === "string"
          ? value.detail
          : JSON.stringify(value.detail ?? value);
    } catch {
      /* Reverse proxies may return HTML; do not render it as trusted content. */
    }
    throw new ApiError(response.status, `${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}
export function prepareMutation(
  path: string,
  payload:
    | Omit<OrderCreate, "idempotency_key">
    | CommandInput
    | Omit<DocumentUpload, "idempotency_key" | "expected_revision">
    | Omit<InvestigationRequest, "idempotency_key" | "expected_revision">,
  label: string,
  revision?: number,
): PreparedMutation {
  return Object.freeze({
    path,
    label,
    body: JSON.stringify({
      ...payload,
      idempotency_key: crypto.randomUUID(),
      ...(revision === undefined ? {} : { expected_revision: revision }),
    }),
  });
}
export const sendMutation = (mutation: PreparedMutation, token: string) =>
  request<OrderView | { run_id: string }>(mutation.path, token, {
    method: "POST",
    body: mutation.body,
  });
export const retryable = (error: unknown) =>
  !(error instanceof ApiError) || error.status >= 500;
export function restoreSession(): Session | undefined {
  try {
    const data = JSON.parse(
      sessionStorage.getItem("jobflow.session") ?? "null",
    );
    return data &&
      typeof data.token === "string" &&
      typeof data.actor?.id === "string"
      ? data
      : undefined;
  } catch {
    return undefined;
  }
}
export function saveSession(session?: Session) {
  try {
    if (session)
      sessionStorage.setItem("jobflow.session", JSON.stringify(session));
    else sessionStorage.removeItem("jobflow.session");
  } catch {
    /* Memory-only operation remains usable when storage is unavailable. */
  }
}
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;
export async function encodeUpload(file: File): Promise<string> {
  if (file.size > MAX_UPLOAD_BYTES)
    throw new Error("Choose a document no larger than 2 MiB.");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192)
    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}
