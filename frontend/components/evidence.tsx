"use client";
import { useEffect, useState } from "react";
import type {
  Evidence,
  OrderView,
  SourceLocation,
} from "../lib/jobflow.generated";
import { API } from "../lib/api";
import { Badge, Button, Drawer } from "./ui";

function ArtifactPreview({
  orderId,
  evidence,
  token,
  page,
  rectangle,
}: {
  orderId: string;
  evidence: Evidence;
  token: string;
  page?: number | null;
  rectangle?: [number, number, number, number] | null;
}) {
  const [url, setUrl] = useState<string>();
  const [pageUrl, setPageUrl] = useState<string>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [requestId, setRequestId] = useState(0);
  const rectangleKey = rectangle?.join(",");
  useEffect(() => {
    if (!requestId) return;
    const controller = new AbortController();
    let blobUrl: string | undefined;
    let renderedUrl: string | undefined;
    setLoading(true);
    setError(undefined);
    void (async () => {
      try {
        const response = await fetch(
          `${API}/orders/${encodeURIComponent(orderId)}/artifacts/${encodeURIComponent(evidence.id)}`,
          {
            headers: { Authorization: `Bearer ${token}` },
            signal: controller.signal,
            cache: "no-store",
          },
        );
        if (!response.ok)
          throw new Error(`Artifact request failed (${response.status}).`);
        const bytes = await response.arrayBuffer();
        const hash = [
          ...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
        ]
          .map((n) => n.toString(16).padStart(2, "0"))
          .join("");
        if (hash !== evidence.sha256)
          throw new Error(
            "Artifact hash mismatch. Inspection blocked; refresh the evidence.",
          );
        if (controller.signal.aborted) return;
        blobUrl = URL.createObjectURL(
          new Blob([bytes], { type: evidence.media_type }),
        );
        setUrl(blobUrl);
        if (evidence.media_type === "application/pdf" && rectangle) {
          const rendered = await fetch(`${API}/orders/${encodeURIComponent(orderId)}/artifacts/${encodeURIComponent(evidence.id)}/pages/${page ?? 1}`,
            { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal, cache: "no-store" });
          if (!rendered.ok || rendered.headers.get("X-Source-SHA256") !== evidence.sha256)
            throw new Error("Rendered page does not match the cited source.");
          const blob = await rendered.blob();
          if (controller.signal.aborted) return;
          renderedUrl = URL.createObjectURL(blob); setPageUrl(renderedUrl);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => {
      controller.abort();
      if (blobUrl) URL.revokeObjectURL(blobUrl);
      if (renderedUrl) URL.revokeObjectURL(renderedUrl);
    };
  }, [
    requestId,
    orderId,
    evidence.id,
    evidence.sha256,
    evidence.media_type,
    token,
    page,
    rectangleKey,
  ]);
  return (
    <div className="artifact-preview">
      {!url && (
        <Button disabled={loading} onClick={() => setRequestId((n) => n + 1)}>
          {loading ? "Verifying bytes…" : "Load verified artifact"}
        </Button>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {url && (
        <>
          <a
            className="button secondary"
            href={`${url}${page ? `#page=${page}` : ""}`}
            target="_blank"
            rel="noreferrer"
          >
            Open verified{" "}
            {evidence.media_type === "application/pdf" ? "PDF" : "artifact"} ↗
          </a>
          <a className="button ghost" href={url} download={evidence.filename}>
            Download
          </a>
          {evidence.media_type === "application/pdf" && (
            pageUrl && rectangle ? <div className="pdf-region-view">
              <img src={pageUrl} alt={`Source page ${page ?? 1}: ${evidence.filename}`} />
              <span aria-label="Cited PDF region" style={{position:"absolute", pointerEvents:"none",
                left:`${rectangle[0]*100}%`, top:`${rectangle[1]*100}%`,
                width:`${(rectangle[2]-rectangle[0])*100}%`, height:`${(rectangle[3]-rectangle[1])*100}%`,
                background:"rgba(255, 200, 40, .3)", outline:"2px solid #d58500"}} />
            </div> : <iframe
              title={`PDF inspection: ${evidence.filename}`}
              src={`${url}#page=${page ?? 1}`}
              className="pdf-preview"
            />
          )}
        </>
      )}
    </div>
  );
}

export function SourceCard({
  order,
  sourceId,
  citation,
  token,
}: {
  order: OrderView;
  sourceId: string;
  citation?: SourceLocation;
  token: string;
}) {
  const evidence = order.evidence.find((e) => e.id === sourceId);
  const valid =
    evidence &&
    (!citation ||
      (evidence.sha256 === citation.sha256 &&
        (evidence.version ?? 1) === citation.version &&
        evidence.text.includes(citation.quote)));
  if (!evidence || !valid)
    return (
      <div className="notice error" role="alert">
        Source unavailable or stale: {sourceId}. This citation does not match
        the current immutable evidence.
      </div>
    );
  return (
    <article className="source-card">
      <div className="row spread">
        <strong>{evidence.filename}</strong>
        <Badge>
          {evidence.authority === "PARTY_ASSERTION"
            ? "Unverified assertion"
            : evidence.authority.replaceAll("_", " ")}
        </Badge>
      </div>
      <p className="muted small">
        {evidence.id} · version {evidence.version ?? 1}
        {citation
          ? ` · ${citation.locator}${citation.page ? ` · page ${citation.page}` : ""}`
          : ""}
      </p>
      <code className="hash">SHA-256 {evidence.sha256}</code>
      {citation?.rectangle && (
        <p className="small muted">
          Cited region: {citation.rectangle.join(", ")}
        </p>
      )}
      <blockquote>{citation ? citation.quote : evidence.text}</blockquote>
      <ArtifactPreview
        key={`${evidence.id}:${evidence.sha256}`}
        orderId={order.id}
        evidence={evidence}
        token={token}
        page={citation?.page}
        rectangle={citation?.rectangle}
      />
    </article>
  );
}
export function CitationList({
  order,
  citations,
  token,
}: {
  order: OrderView;
  citations: SourceLocation[];
  token: string;
}) {
  return (
    <>
      {citations.map((citation, index) => (
        <SourceCard
          key={`${citation.source_id}:${index}`}
          order={order}
          sourceId={citation.source_id}
          citation={citation}
          token={token}
        />
      ))}
    </>
  );
}
export function EvidenceDrawer({
  order,
  token,
}: {
  order: OrderView;
  token: string;
}) {
  return (
    <Drawer
      title="Evidence library"
      description="Immutable source versions. Party uploads are not accepted authority."
      wide
      trigger={<Button>Evidence library ↗</Button>}
    >
      {order.evidence.map((e) => (
        <details key={e.id}>
          <summary>
            {e.filename} · v{e.version ?? 1} · {e.kind}
          </summary>
          <SourceCard order={order} sourceId={e.id} token={token} />
        </details>
      ))}
    </Drawer>
  );
}
