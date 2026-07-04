// src/types/contracts.ts
export type AppId =
  | "dashboard" | "pipelines" | "assignments" | "org" | "questions" | "lectures"
  | "booklets" | "insp" | "sims" | "mycontentdev" | "munshi" | "activity"
  | "settings" | "terminal" | "clock" | "notes" | "snake" | "atlas" | "publish";

// G3: a PRATHAM student identity (the /api/learn/me + login shape).
export interface Student { id: string; name: string; }

export interface AppMeta { id: AppId; name: string; accent: string; w: number; h: number; }
export interface Rect { x: number; y: number; w: number; h: number; }
export interface WindowState {
  id: string; app: AppId; x: number; y: number; w: number; h: number;
  z: number; min: boolean; max: boolean; prev: Rect | null;
}
export type Theme = "aqua" | "console" | "samagra";
export type Device = "pc" | "mobile";

export const MIN_W = 360;
export const MIN_H = 280;

// Terminal
export type LineClass = "in" | "fg" | "dim" | "accent" | "ok" | "err";
export interface TermLine { t: string; c: LineClass; }
export type TermEffect =
  | { kind: "openApp"; value: AppId }
  | { kind: "setTheme"; value: Theme }
  | { kind: "setDevice"; value: Device };
export interface TermCtx { order: AppId[]; apps: Record<AppId, AppMeta>; }

// Notes / todos
export interface Note { id: string; title: string; body: string; ts: number; }
export interface Todo { id: string; text: string; done: boolean; }
export type TodoFilter = "all" | "active" | "done";

// Backend
export interface ApiClient {
  overview(): Promise<unknown>;
  pipelines(): Promise<unknown>;
  assignments(): Promise<unknown>;
}

// ── Catalog / search (GET /api/search, /api/facets) ──────────────────────────
export interface SearchResult {
  uid: string; source: string; kind: string; title: string;
  subject: string | null; unit: string | null; chapter: string | null;
  status: string | null; path: string | null; url: string | null;
  updated_at: string | null;
  meta: Record<string, unknown>;     // parsed from meta_json
  meta_json?: string;                 // raw string ALSO present on the wire
}
export interface SearchResponse { results: SearchResult[]; }
export interface Facets { sources: string[]; kinds: string[]; subjects: string[]; }

// ── Questions (GET /api/questions) — proxied from the live QX engine ──────────
export type QuestionMode = "exact" | "semantic";
export interface Question {
  q_uid: string; slug: string; q_type: string | null;
  subject: string | null; chapter: string | null; difficulty: string | null;
  snippet: string;   // flat text_projection preview
  html: string;      // QX-rendered question HTML (KaTeX maths + figure <img>)
}
export type FacetPair = [string, number];   // [value, count]
export interface QuestionFacetCounts {
  subject: FacetPair[]; chapter: FacetPair[]; qtype: FacetPair[];
}
export interface QuestionsResponse {
  results: Question[];
  total: number; page: number; page_size: number;
  mode: QuestionMode; degraded: boolean;     // degraded = semantic asked, exact served
  facets: QuestionFacetCounts;
  error?: string;                            // present (HTTP 200) when QX is unreachable
}

// ── Overview (GET /api/overview) — promote Dashboard's inline types ───────────
export interface OverviewSource {
  source: string; label: string; available: number;   // 0 | 1
  n_artifacts: number; refreshed_at: string;
  summary: Record<string, unknown>;
  summary_json?: string;             // raw string ALSO present on the wire
}
export interface Overview { sources: OverviewSource[]; refreshed_at: string | null; }

// ── Pipelines (GET /api/pipelines) ───────────────────────────────────────────
export type PipelineStatus = "pending" | "in_progress" | "awaiting_gate" | "done" | "failed" | "blocked";
export interface Phase {
  status: PipelineStatus; owner: string | null; gate: boolean;
  started: string | null; finished: string | null; artifacts: string[]; error: string | null;
}
export interface Pipeline {
  pipeline: string; label: string; created: string; updated: string;
  current: string; phases: Record<string, Phase>;     // keyed by phase NAME, not array
}
export interface PipelinesResponse { pipelines: Pipeline[]; }

// ── Assignments + events (GET /api/assignments) ──────────────────────────────
export type AssignmentStatus = "queued" | "running" | "in-review" | "approved" | "changes";  // HYPHEN
export interface Assignment {
  id: string; agent: string; outbox_path: string;
  pipeline: string | null; seed_ref: string | null; artifact_ref: string | null;
  expected_output: string | null; review_by: string | null;
  status: AssignmentStatus; created_at: string; updated_at: string;
}
export interface EventItem {
  id: number; ts: string; actor: string; verb: string;
  assignment_id: string | null; subsystem: string | null; subsystem_ref: string | null; note: string | null;
}
export interface AssignmentsResponse { assignments: Assignment[]; events: EventItem[]; }

// ── Org chart (GET /api/org — built in E2.1; shape mirrors samagra/org.py) ────
export interface OrgPerson { id: string; name: string; role: string; }
export interface OrgChart {
  chairman: OrgPerson; board: OrgPerson[]; workers: OrgPerson[];
  owners: Record<string, { name: string; role: string }>;  // token -> identity (7 owner ids)
}

// ── Capture / sims / facets (control-plane: POST capture + read-only sims/facets) ──
export type MunshiKind = "todo" | "note" | "followup";
export interface MunshiCaptureForm { kind: MunshiKind; [field: string]: string; }
export interface SeedForm { type: SeedType; title?: string; raw_text: string; source_ref?: string; }
export type SeedType =
  | "concept" | "question" | "snippet" | "simulation_idea"
  | "experiment" | "notebooklm_link" | "rough_idea";
export interface SimRow { id: string; title: string; subject: string | null; grade: string | null; url: string; }
export interface SimsResponse { sims: SimRow[]; total: number; }
export interface QuestionFacets { subjects: string[]; }

// ── Atlas / coverage graph (GET /api/coverage) — Phase E ─────────────────────
export type CoverageState = "produced" | "base" | "gap";
export interface CoverageConcept {
  concept_id: number; label: string; chapter_id: string | null;
  demand_size: number; paper_count: number;
}
export interface CoverageCell {
  concept_id: number; lane: string; state: CoverageState;
  produced_n: number; base_n: number;
}
export interface CoverageGap {
  rank: number; concept_id: number; lane: string; cell_state: "base" | "gap";
  demand_size: number; existing_corpus_n: number; deficit_score: number;
  suggested_seed_ref: string; plan_command: string;
}
export interface CoverageResponse {
  lanes: string[];
  concepts: CoverageConcept[];
  cells: CoverageCell[];
  gaps: CoverageGap[];
  meta: Record<string, unknown>;
  error?: string;
}
