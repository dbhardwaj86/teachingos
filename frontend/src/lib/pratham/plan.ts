// frontend/src/lib/pratham/plan.ts
// G4: thin typed wrappers over the session-gated adaptive endpoints (mirrors
// session.ts — same-origin credentials, null/false on any failure so the reader
// degrades to anonymous behavior instead of crashing).
export interface NextItem {
  chapter: string; title: string; lane: string;
  reason: string; score: number; rank: number;
}
export interface ProgressRow { chapter: string; lane: string; status: string; marked_at: string; }
export interface NextResponse { queue: NextItem[]; done: ProgressRow[]; }

export async function nextRequest(): Promise<NextResponse | null> {
  try {
    const r = await fetch("/api/learn/next", { credentials: "same-origin" });
    if (!r.ok) return null;
    return (await r.json()) as NextResponse;
  } catch { return null; }
}

export async function markDoneRequest(chapter: string, lane: string): Promise<boolean> {
  try {
    const r = await fetch("/api/learn/progress", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapter, lane }),
    });
    return r.ok;
  } catch { return false; }
}
