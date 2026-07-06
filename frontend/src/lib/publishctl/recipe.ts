// frontend/src/lib/publishctl/recipe.ts
// PURE stepper-state derivation for the G5 "Factory run" panel + thin typed fetch
// wrappers over the 3 new owner-gated endpoints. No React (headless-tested),
// mirroring the existing rows.ts convention in this same directory.

export interface AssignmentLike {
  id?: string;
  pipeline?: string;
  status?: string;
}

export type RecipeStep = "plan" | "approve" | "build" | "publish";

// Mirrors samagra/factory/lines.py's _ORDER (deterministic-lane prefix only —
// seed/samadhan are CLI-only/opt-in, never proposed by the plan step here; the
// server 403s a build attempt against them anyway). Also mirrors the Saar-led
// LANE_ORDER convention in frontend/src/lib/published/manifest.ts — keep in sync.
const _LANE_ORDER = ["revision", "lecture", "deck", "paper", "drill"];
const _laneRank = (p: string | undefined) => {
  const i = _LANE_ORDER.indexOf(p ?? "");
  return i === -1 ? 99 : i;
};

export function deriveStep(rows: AssignmentLike[] | null | undefined): RecipeStep {
  const list = Array.isArray(rows) ? rows : [];
  if (list.length === 0) return "plan";
  if (list.some((r) => r.status === "in-review")) return "approve";
  if (list.some((r) => r.status === "approved")) return "build";
  return "publish";
}

export function nextAssignmentToBuild(rows: AssignmentLike[] | null | undefined): string | null {
  const list = Array.isArray(rows) ? rows : [];
  const approved = list.filter((r) => r.status === "approved" && r.id);
  if (approved.length === 0) return null;
  approved.sort((a, b) => _laneRank(a.pipeline) - _laneRank(b.pipeline));
  return approved[0].id as string;
}

async function _postOrThrow<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { const j = await r.json(); if (j?.detail) detail = String(j.detail); } catch { /* keep detail */ }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

export interface PlanProposal {
  seed_ref: string; line: string; expected_output: string;
  assignment_id?: string; reused?: boolean;
}
export interface PlanResponse { proposals: PlanProposal[]; }
export interface ApproveSeedResponse { seed_ref: string; approved: string[]; }
export interface BuildResponse {
  assignment_id?: string; line: string; artifact_ref: string; status?: string;
}

export function planRequest(seedRef: string): Promise<PlanResponse> {
  return _postOrThrow<PlanResponse>("/api/factory/plan", { seed_ref: seedRef });
}

export function approveSeedRequest(seedRef: string): Promise<ApproveSeedResponse> {
  return _postOrThrow<ApproveSeedResponse>("/api/factory/approve-seed", { seed_ref: seedRef });
}

export function buildRequest(assignmentId: string): Promise<BuildResponse> {
  return _postOrThrow<BuildResponse>("/api/factory/build", { assignment_id: assignmentId });
}
