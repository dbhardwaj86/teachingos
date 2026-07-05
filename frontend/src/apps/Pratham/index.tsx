// The PRATHAM reader — the Phase G2 student surface. A separate full-page
// experience (mounted at /learn, NO operator OS-shell chrome) that reads ONLY the
// public /api/published surface. The Saar (revision) sheet leads; each lane's
// self-contained HTML renders in a sandboxed iframe (origin-isolated from the app).
import { useEffect, useRef, useState } from "react";
import type { Student } from "../../types/contracts";
import { loginRequest, logoutRequest, meRequest } from "../../lib/pratham/session";
import { markDoneRequest, nextRequest, type NextResponse } from "../../lib/pratham/plan";
import { useApi } from "../../hooks/useApi";
import {
  artifactUrl, chaptersList, fileExts, laneLabel, laneSort, pickChapter, pickLane,
  type PublishedManifest,
} from "../../lib/published/manifest";
import { learnPath, parseLearnPath } from "../../lib/published/route";

const C = {
  bg: "#fbfbfd", text: "#1c1c28", muted: "#6b7280", line: "#e6e6ef",
  accent: "#2563eb", card: "#ffffff",
  font: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
};

export default function Pratham() {
  const { data, loading, error } = useApi<PublishedManifest>("/api/published");
  const chapters = chaptersList(data);
  const [sel, setSel] = useState(() => parseLearnPath(window.location.pathname));

  // G3: additive student identity. Anonymous reading is unchanged; a signed-in
  // student gets a small shell header (their name + sign out). The corpus renders
  // regardless of session.
  const [student, setStudent] = useState<Student | null>(null);
  const [signinOpen, setSigninOpen] = useState(false);
  const [code, setCode] = useState("");
  const [authErr, setAuthErr] = useState<string | null>(null);
  // A slow mount hydration must NOT clobber a login/logout that already resolved.
  const meResolved = useRef(false);

  useEffect(() => {
    let alive = true;
    meRequest().then((s) => {
      if (alive && !meResolved.current) setStudent(s);
      meResolved.current = true;
    });
    return () => { alive = false; };
  }, []);

  async function doLogin() {
    setAuthErr(null);
    try {
      const r = await loginRequest(code.trim());
      setStudent(r.student);
      meResolved.current = true;   // authoritative ONLY on success; a failed attempt leaves hydration free to restore a valid session
      setSigninOpen(false);
      setCode("");
    } catch {
      setAuthErr("That code didn't work. Check it and try again.");
    }
  }

  async function doLogout() {
    meResolved.current = true;
    try { await logoutRequest(); } finally { setStudent(null); }
  }

  const chapter = pickChapter(chapters, sel.chapter);
  const lanes = chapter ? laneSort(chapter.artifacts.map((a) => a.lane)) : [];
  const lane = pickLane(lanes, sel.lane);
  const artifact = chapter?.artifacts.find((a) => a.lane === lane);
  const hasDocx = fileExts(artifact).includes("docx");

  // G4: the adaptive plan — fetched ONLY for a signed-in student (F-G4-4). An
  // anonymous reader never calls /api/learn/next and renders zero adaptive UI.
  // A generation counter guards against a late-resolving fetch (e.g. markDone's
  // refetch racing a sign-out/sign-in) repopulating the plan for a DIFFERENT
  // student on the same device — see review finding on stale plan bleed.
  const [plan, setPlan] = useState<NextResponse | null>(null);
  const planGen = useRef(0);
  useEffect(() => {
    planGen.current += 1;               // invalidate any in-flight plan fetch
    if (!student) { setPlan(null); return; }
    const gen = planGen.current;
    let alive = true;
    nextRequest().then((p) => { if (alive && planGen.current === gen) setPlan(p); });
    return () => { alive = false; };
  }, [student]);

  async function markDone() {
    if (!chapter || !lane) return;
    const gen = planGen.current;
    if (await markDoneRequest(chapter.chapter, lane)) {
      const p = await nextRequest();          // refetch: the loop closes here
      if (planGen.current === gen) setPlan(p);   // stale after sign-out/in — drop
    }
  }
  const doneSet = new Set((plan?.done ?? []).map((d) => `${d.chapter}:${d.lane}`));

  // MVP nav: pushState keeps the URL shareable/deep-linkable, but we deliberately
  // do NOT add a popstate listener (back/forward won't re-sync selection) — a known
  // G2 scope choice. The palette is a standalone PRATHAM palette (NOT operator theme
  // tokens) on purpose: /learn is a separate student surface, not the OS console.
  function go(nextChapter?: string, nextLane?: string) {
    setSel({ chapter: nextChapter, lane: nextLane });
    window.history.pushState(null, "", learnPath(nextChapter, nextLane));
  }

  return (
    <div data-testid="pratham" style={{
      position: "fixed", inset: 0, display: "flex", flexDirection: "column",
      background: C.bg, color: C.text, font: `15px ${C.font}`,
    }}>
      <header style={{
        padding: "14px 22px", borderBottom: `1px solid ${C.line}`,
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <strong style={{ fontSize: 18, letterSpacing: 0.2 }}>PRATHAM</strong>
        <span style={{ color: C.muted, fontSize: 13 }}>Published revision corpus</span>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          {student ? (
            <>
              <span data-testid="pratham-user" style={{ fontSize: 13, color: C.muted }}>
                Signed in as {student.name}
              </span>
              <button data-testid="pratham-signout" onClick={doLogout}
                style={{ border: `1px solid ${C.line}`, background: C.card, color: C.text,
                  font: "inherit", padding: "5px 10px", borderRadius: 8, cursor: "pointer" }}>
                Sign out
              </button>
            </>
          ) : signinOpen ? (
            <>
              <input data-testid="pratham-signin-input" value={code}
                onChange={(e) => setCode(e.target.value)} placeholder="Enter your code"
                onKeyDown={(e) => { if (e.key === "Enter") doLogin(); }}
                aria-label="enrollment code"
                style={{ font: "inherit", padding: "5px 8px", borderRadius: 8,
                  border: `1px solid ${C.line}` }} />
              <button data-testid="pratham-signin-submit" onClick={doLogin}
                style={{ border: 0, background: C.accent, color: "#fff", font: "inherit",
                  padding: "6px 12px", borderRadius: 8, cursor: "pointer" }}>
                Go
              </button>
              {authErr ? (
                <span data-testid="pratham-signin-error" role="alert"
                  style={{ fontSize: 12, color: "#b91c1c" }}>{authErr}</span>
              ) : null}
            </>
          ) : (
            <button data-testid="pratham-signin" onClick={() => setSigninOpen(true)}
              style={{ border: `1px solid ${C.line}`, background: C.card, color: C.text,
                font: "inherit", padding: "5px 10px", borderRadius: 8, cursor: "pointer" }}>
              Sign in
            </button>
          )}
        </div>
      </header>

      {chapters.length === 0 ? (
        error && !loading ? (
          <div data-testid="pratham-error" role="alert" style={{
            margin: "auto", color: C.muted, textAlign: "center", padding: 40,
          }}>
            Couldn't load the published corpus — please try again later.
          </div>
        ) : (
          <div data-testid="pratham-empty" aria-busy={loading} style={{
            margin: "auto", color: C.muted, textAlign: "center", padding: 40,
          }}>
            {loading ? "Loading…" : "Nothing published yet."}
          </div>
        )
      ) : (
        <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
          <nav style={{
            width: 240, borderRight: `1px solid ${C.line}`, overflowY: "auto", padding: 10,
          }}>
            {chapters.map((c) => (
              <button key={c.chapter} data-testid={`pratham-chapter-${c.chapter}`}
                onClick={() => go(c.chapter, undefined)}
                style={{
                  display: "block", width: "100%", textAlign: "left", border: 0,
                  background: c.chapter === chapter?.chapter
                    ? `color-mix(in srgb, ${C.accent} 12%, transparent)` : "transparent",
                  color: C.text, font: "inherit", padding: "8px 10px",
                  borderRadius: 8, cursor: "pointer",
                }}>
                {c.title ?? c.chapter}
              </button>
            ))}
          </nav>

          <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
            <div style={{
              display: "flex", gap: 6, padding: "10px 14px", flexWrap: "wrap",
              borderBottom: `1px solid ${C.line}`, alignItems: "center",
            }}>
              {lanes.map((l) => {
                const lab = laneLabel(l);
                return (
                  <button key={l} data-testid={`pratham-lane-${l}`}
                    onClick={() => go(chapter?.chapter, l)} title={lab.gloss}
                    style={{
                      border: `1px solid ${l === lane ? C.accent : C.line}`,
                      background: l === lane ? C.accent : C.card,
                      color: l === lane ? "#fff" : C.text, font: "inherit",
                      padding: "6px 12px", borderRadius: 999, cursor: "pointer",
                    }}>
                    {lab.name}
                  </button>
                );
              })}
              {student && chapter && lane ? (
                doneSet.has(`${chapter.chapter}:${lane}`) ? (
                  <span data-testid="pratham-done-badge"
                    style={{ fontSize: 13, color: "#15803d", fontWeight: 600 }}>
                    Done
                  </span>
                ) : (
                  <button data-testid="pratham-mark-done" onClick={markDone}
                    style={{ border: `1px solid ${C.line}`, background: C.card,
                      color: C.text, font: "inherit", padding: "6px 12px",
                      borderRadius: 999, cursor: "pointer" }}>
                    Mark done
                  </button>
                )
              ) : null}
              {hasDocx && chapter && lane ? (
                <a data-testid="pratham-docx"
                  href={artifactUrl(chapter.chapter, lane, "docx")}
                  style={{ marginLeft: "auto", color: C.accent, fontSize: 13 }}>
                  Download original (.docx)
                </a>
              ) : null}
            </div>
            {student && plan && plan.queue.length > 0 ? (
              <div data-testid="pratham-next" style={{
                display: "flex", gap: 6, padding: "8px 14px", flexWrap: "wrap",
                alignItems: "center", borderBottom: `1px solid ${C.line}`,
                fontSize: 13,
              }}>
                <span style={{ color: C.muted }}>What's next:</span>
                {plan.queue.slice(0, 5).map((g) => (
                  <button key={`${g.chapter}:${g.lane}`}
                    data-testid={`pratham-next-${g.chapter}-${g.lane}`}
                    onClick={() => go(g.chapter, g.lane)} title={g.reason}
                    style={{ border: `1px solid ${C.line}`, background: C.card,
                      color: C.text, font: "inherit", padding: "4px 10px",
                      borderRadius: 999, cursor: "pointer" }}>
                    {g.title} · {laneLabel(g.lane).name}
                  </button>
                ))}
              </div>
            ) : null}
            {chapter && lane ? (
              <iframe data-testid="pratham-frame"
                title={`${chapter.title ?? chapter.chapter} — ${laneLabel(lane).name}`}
                src={artifactUrl(chapter.chapter, lane)}
                sandbox="allow-scripts"
                referrerPolicy="no-referrer"
                style={{ flex: 1, border: 0, width: "100%", background: "#fff" }} />
            ) : null}
          </main>
        </div>
      )}
    </div>
  );
}
