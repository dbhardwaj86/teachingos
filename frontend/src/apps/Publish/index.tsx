// frontend/src/apps/Publish/index.tsx
// G3 minimal operator Publish control: list captured textbook chapters (with which
// lanes are captured + which are already published) and publish / unpublish each
// through the OWNER-GATED POST /api/factory/publish|unpublish. The CLI remains the
// power path; this is the thin GUI sibling.
import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { useApiPost } from "../../hooks/useApiPost";
import { publishRows, type AssignmentLike, type PublishedManifestLike } from "../../lib/publishctl/rows";
import {
  approveSeedRequest, buildRequest, deriveStep, isDeterministicLane, nextAssignmentToBuild,
  planRequest, type AssignmentLike as RecipeAssignmentLike,
} from "../../lib/publishctl/recipe";

export default function Publish() {
  const [nonce, setNonce] = useState(0);
  // useApi refetches when the path changes -> a cache-busting nonce reloads both
  // sources after a publish/unpublish.
  // /api/assignments returns {assignments, events} (samagra/api/app.py) — never
  // a bare array; unwrap before the pure merge.
  const asg = useApi<{ assignments?: AssignmentLike[] }>(`/api/assignments?_=${nonce}`);
  const man = useApi<PublishedManifestLike>(`/api/published?_=${nonce}`);
  const { post, error, loading: posting } = useApiPost<{ ok: boolean }>();
  const rows = publishRows(asg.data?.assignments, man.data);

  async function act(path: string, chapter: string) {
    const r = await post(path, { chapter });
    if (r) setNonce((n) => n + 1);
  }

  // --- G5 "Factory run" stepper panel -------------------------------------
  const [slug, setSlug] = useState("");
  const [stepResult, setStepResult] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);
  // In-flight guard for the panel's own handlers: while any step request is
  // pending, every stepper button is disabled so a double-click can't stomp
  // the result line or start a second concurrent build loop (whose first call
  // would 409 on the server's in-flight guard with a misleading error).
  const [isRunning, setIsRunning] = useState(false);

  const seedRef = `textbook:${slug.trim()}`;
  const rowsForSeed: RecipeAssignmentLike[] = (asg.data?.assignments ?? [])
    .filter((a) => (a as { seed_ref?: string }).seed_ref === seedRef)
    .map((a) => ({
      id: (a as { id?: string }).id, pipeline: (a as { pipeline?: string }).pipeline,
      status: (a as { status?: string }).status,
    }))
    // Deterministic-lane filter (controller ruling): a CLI-planned samadhan/seed
    // row for the same seed must never distort the derived step.
    .filter((r) => isDeterministicLane(r.pipeline));
  const step = slug.trim() ? deriveStep(rowsForSeed) : "plan";

  async function doPlan() {
    setStepError(null); setStepResult(null); setIsRunning(true);
    try {
      const r = await planRequest(seedRef);
      setStepResult(`planned ${r.proposals.length} lane(s)`);
      setNonce((n) => n + 1);
    } catch (e) { setStepError(String((e as Error).message ?? e)); }
    finally { setIsRunning(false); }
  }

  async function doApproveSeed() {
    setStepError(null); setStepResult(null); setIsRunning(true);
    try {
      const r = await approveSeedRequest(seedRef);
      setStepResult(`approved ${r.approved.length}`);
      setNonce((n) => n + 1);
    } catch (e) { setStepError(String((e as Error).message ?? e)); }
    finally { setIsRunning(false); }
  }

  async function doBuildAll() {
    setStepError(null); setStepResult(null); setIsRunning(true);
    try {
      let built = 0;
      let current = rowsForSeed;
      let next = nextAssignmentToBuild(current);
      while (next) {
        try {
          await buildRequest(next);
          built += 1;
        } catch (e) {
          setStepError(`built ${built} then failed: ${String((e as Error).message ?? e)}`);
          setNonce((n) => n + 1);
          return;
        }
        // Re-derive from the freshly-known state: mark this id as no longer
        // approved so the loop terminates without waiting on a network refetch
        // mid-loop (the panel still triggers ONE refetch at the end for the
        // captured/published table + stepper to reflect reality).
        current = current.map((r) => (r.id === next ? { ...r, status: "captured" } : r));
        next = nextAssignmentToBuild(current);
      }
      setStepResult(`built ${built}`);
      setNonce((n) => n + 1);
    } finally { setIsRunning(false); }
  }

  return (
    <div style={{ padding: 16, font: "14px 'Inter', system-ui, sans-serif", color: "#1c1c28" }}>
      <h2 style={{ margin: "0 0 4px" }}>Publish</h2>
      <p style={{ color: "#6b7280", marginTop: 0 }}>
        Release captured chapters to the public <code>/learn</code> corpus. Owner-gated; never automated.
      </p>
      {error ? <p role="alert" style={{ color: "#b91c1c" }}>{error}</p> : null}
      <div style={{ border: "1px solid #e6e6ef", borderRadius: 8, padding: 12, marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 15 }}>Factory run</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input data-testid="factory-run-slug" value={slug} aria-label="chapter slug"
            onChange={(e) => setSlug(e.target.value)}
            placeholder="chapter slug, e.g. circular-motion"
            style={{ padding: "5px 8px", border: "1px solid #e6e6ef", borderRadius: 6, minWidth: 220 }} />
          <button data-testid="factory-run-plan" disabled={!slug.trim() || step !== "plan" || isRunning}
            onClick={doPlan}
            style={{ border: 0, background: step === "plan" ? "#2563eb" : "#c7d2fe",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Plan
          </button>
          <button data-testid="factory-run-approve" disabled={!slug.trim() || step !== "approve" || isRunning}
            onClick={doApproveSeed}
            style={{ border: 0, background: step === "approve" ? "#2563eb" : "#c7d2fe",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Approve seed
          </button>
          <button data-testid="factory-run-build" disabled={!slug.trim() || step !== "build" || isRunning}
            onClick={doBuildAll}
            style={{ border: 0, background: step === "build" ? "#2563eb" : "#c7d2fe",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Build all
          </button>
          {/* Publish delegates to the shared async act(); gate on useApiPost's
              own loading flag too so an in-flight publish also disables it. */}
          <button data-testid="factory-run-publish"
            disabled={!slug.trim() || step !== "publish" || isRunning || posting}
            onClick={() => act("/api/factory/publish", slug.trim())}
            style={{ border: 0, background: step === "publish" ? "#16a34a" : "#bbf7d0",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Publish
          </button>
        </div>
        {stepResult ? (
          <p data-testid="factory-run-result" style={{ color: "#16a34a", margin: "8px 0 0" }}>{stepResult}</p>
        ) : null}
        {stepError ? (
          <p data-testid="factory-run-error" role="alert" style={{ color: "#b91c1c", margin: "8px 0 0" }}>{stepError}</p>
        ) : null}
      </div>
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
