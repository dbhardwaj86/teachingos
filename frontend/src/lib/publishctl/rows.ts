// frontend/src/lib/publishctl/rows.ts
// PURE merge of captured factory assignments x the published manifest -> the rows
// the operator Publish control renders. No fetch, no React (headless-tested).

export interface AssignmentLike { seed_ref?: string; pipeline?: string; status?: string; }
export interface PublishedManifestLike {
  chapters?: Record<string, { chapter?: string; title?: string;
    artifacts?: Array<{ lane?: string }> }>;
}
export interface PublishRow {
  chapter: string;
  title: string;
  capturedLanes: string[];   // lanes captured-and-publishable (textbook seeds)
  publishedLanes: string[];  // lanes currently in the published manifest
}

const _TEXTBOOK = "textbook:";

export function publishRows(
  assignments: AssignmentLike[] | null | undefined,
  manifest: PublishedManifestLike | null | undefined,
): PublishRow[] {
  const captured = new Map<string, Set<string>>();
  // Defensive: a non-array (e.g. the whole {assignments, events} response object
  // passed by mistake) must degrade to "no rows", never throw mid-render.
  const list = Array.isArray(assignments) ? assignments : [];
  for (const a of list) {
    if (a?.status !== "captured") continue;
    const ref = a?.seed_ref ?? "";
    if (!ref.startsWith(_TEXTBOOK)) continue;
    const chapter = ref.slice(_TEXTBOOK.length);
    const lane = a?.pipeline;
    if (!chapter || !lane) continue;
    (captured.get(chapter) ?? captured.set(chapter, new Set()).get(chapter)!).add(lane);
  }
  const chapters = manifest?.chapters ?? {};
  const rows: PublishRow[] = [];
  for (const [chapter, lanes] of captured) {
    const m = chapters[chapter];
    const publishedLanes = (m?.artifacts ?? [])
      .map((x) => x?.lane).filter((l): l is string => !!l).sort();
    rows.push({
      chapter,
      title: m?.title ?? chapter,
      capturedLanes: [...lanes].sort(),
      publishedLanes,
    });
  }
  rows.sort((a, b) => a.chapter.localeCompare(b.chapter));
  return rows;
}
