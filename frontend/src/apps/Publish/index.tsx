// frontend/src/apps/Publish/index.tsx
// G3 minimal operator Publish control: list captured textbook chapters (with which
// lanes are captured + which are already published) and publish / unpublish each
// through the OWNER-GATED POST /api/factory/publish|unpublish. The CLI remains the
// power path; this is the thin GUI sibling.
import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { useApiPost } from "../../hooks/useApiPost";
import { publishRows, type AssignmentLike, type PublishedManifestLike } from "../../lib/publishctl/rows";

export default function Publish() {
  const [nonce, setNonce] = useState(0);
  // useApi refetches when the path changes -> a cache-busting nonce reloads both
  // sources after a publish/unpublish.
  // /api/assignments returns {assignments, events} (samagra/api/app.py) — never
  // a bare array; unwrap before the pure merge.
  const asg = useApi<{ assignments?: AssignmentLike[] }>(`/api/assignments?_=${nonce}`);
  const man = useApi<PublishedManifestLike>(`/api/published?_=${nonce}`);
  const { post, error } = useApiPost<{ ok: boolean }>();
  const rows = publishRows(asg.data?.assignments, man.data);

  async function act(path: string, chapter: string) {
    const r = await post(path, { chapter });
    if (r) setNonce((n) => n + 1);
  }

  return (
    <div style={{ padding: 16, font: "14px 'Inter', system-ui, sans-serif", color: "#1c1c28" }}>
      <h2 style={{ margin: "0 0 4px" }}>Publish</h2>
      <p style={{ color: "#6b7280", marginTop: 0 }}>
        Release captured chapters to the public <code>/learn</code> corpus. Owner-gated; never automated.
      </p>
      {error ? <p role="alert" style={{ color: "#b91c1c" }}>{error}</p> : null}
      {rows.length === 0 ? (
        <p data-testid="publish-empty" style={{ color: "#6b7280" }}>
          No captured chapters yet — build a chapter through the factory first.
        </p>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e6e6ef" }}>
              <th style={{ padding: "6px 8px" }}>Chapter</th>
              <th style={{ padding: "6px 8px" }}>Captured</th>
              <th style={{ padding: "6px 8px" }}>Published</th>
              <th style={{ padding: "6px 8px" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.chapter} style={{ borderBottom: "1px solid #f1f1f6" }}>
                <td style={{ padding: "6px 8px" }}>{r.title}</td>
                <td style={{ padding: "6px 8px", color: "#6b7280" }}>{r.capturedLanes.join(", ")}</td>
                <td style={{ padding: "6px 8px", color: "#16a34a" }}>
                  {r.publishedLanes.length ? r.publishedLanes.join(", ") : "—"}
                </td>
                <td style={{ padding: "6px 8px", display: "flex", gap: 6 }}>
                  <button data-testid={`publish-${r.chapter}`}
                    onClick={() => act("/api/factory/publish", r.chapter)}
                    style={{ border: 0, background: "#16a34a", color: "#fff", borderRadius: 6,
                      padding: "5px 10px", cursor: "pointer" }}>
                    Publish all captured
                  </button>
                  {r.publishedLanes.length ? (
                    <button data-testid={`unpublish-${r.chapter}`}
                      onClick={() => act("/api/factory/unpublish", r.chapter)}
                      style={{ border: "1px solid #e6e6ef", background: "#fff", color: "#1c1c28",
                        borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
                      Unpublish
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
