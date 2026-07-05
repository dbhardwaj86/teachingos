// Pure helpers + types over the G1 `samagra.published.v1` export contract.
// Zero React, zero DOM — fully headless-testable (the PRATHAM reader's logic core).

export interface PublishedFile {
  rel: string;
  sha256: string;
  bytes: number;
}
export interface PublishedArtifact {
  uid: string;
  lane: string;
  assignment_id: string;
  files: PublishedFile[];
  source_seed_ref: string;
  style_seed_version: string | null;
  captured_at: string | null;
  published_at: string | null;
  publication_id: string;
}
export interface PublishedChapter {
  chapter: string;
  title: string | null;
  seed_ref: string | null;
  artifacts: PublishedArtifact[];
}
export interface PublishedManifest {
  schema: string;
  generated_at: string | null;
  publication_count: number;
  chapters: Record<string, PublishedChapter>;
}

// Saar-led canonical lane order; unknown lanes sort after, alphabetically.
// Mirrored in samagra/factory/coverage/next_best.py (_LANE_PRIORITY) — keep in sync.
export const LANE_ORDER = ["revision", "lecture", "deck", "paper", "drill", "samadhan"];

const LANE_LABELS: Record<string, { name: string; gloss: string }> = {
  revision: { name: "Saar", gloss: "Revision sheet" },
  lecture: { name: "Vaani", gloss: "Lecture" },
  deck: { name: "Smriti", gloss: "Flashcards" },
  paper: { name: "Pariksha", gloss: "Practice paper" },
  drill: { name: "Abhyaas", gloss: "Drill" },
  samadhan: { name: "Samadhan", gloss: "Solutions" },
};

function titlecase(s: string): string {
  return s.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function laneLabel(lane: string): { name: string; gloss: string } {
  return LANE_LABELS[lane] ?? { name: titlecase(lane), gloss: "" };
}

export function laneSort(lanes: string[]): string[] {
  const rank = (l: string) => {
    const i = LANE_ORDER.indexOf(l);
    return i === -1 ? LANE_ORDER.length : i;
  };
  return [...new Set(lanes)].sort((a, b) => {
    const ra = rank(a), rb = rank(b);
    return ra !== rb ? ra - rb : a.localeCompare(b);
  });
}

export function chaptersList(m: PublishedManifest | null | undefined): PublishedChapter[] {
  const chapters = m?.chapters;
  if (!chapters || typeof chapters !== "object") return [];
  return Object.values(chapters)
    .filter((c): c is PublishedChapter => !!c && Array.isArray(c.artifacts))
    .sort((a, b) => (a.title ?? a.chapter).localeCompare(b.title ?? b.chapter));
}

export function pickChapter(
  chapters: PublishedChapter[], slug?: string,
): PublishedChapter | undefined {
  if (slug) {
    const hit = chapters.find((c) => c.chapter === slug);
    if (hit) return hit;
  }
  return chapters[0];
}

export function pickLane(lanes: string[], lane?: string): string | undefined {
  if (lane && lanes.includes(lane)) return lane;
  return lanes[0];
}

export function fileExts(artifact: PublishedArtifact | undefined): string[] {
  if (!artifact || !Array.isArray(artifact.files)) return [];
  return artifact.files
    .map((f) => {
      const m = /\.([A-Za-z0-9]+)$/.exec(f.rel || "");
      return m ? m[1].toLowerCase() : "";
    })
    .filter(Boolean);
}

export function artifactUrl(chapter: string, lane: string, kind?: string): string {
  const base = `/api/published/${encodeURIComponent(chapter)}/${encodeURIComponent(lane)}`;
  return kind && kind !== "html" ? `${base}?kind=${encodeURIComponent(kind)}` : base;
}
