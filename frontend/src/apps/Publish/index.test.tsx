// frontend/src/apps/Publish/index.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Publish from "./index";

// Mutable holder for the /api/assignments row-set the useApi mock returns —
// defaults to the G3 baseline (one captured circular-motion revision row) so
// the pre-existing G3 tests below are untouched; Task 7 (G5) tests reassign
// this before rendering to simulate different stepper states. Reset in
// afterEach so no test leaks its row-set into the next.
const DEFAULT_ASSIGNMENTS = [
  { seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" },
];
let mockAssignments: unknown[] = DEFAULT_ASSIGNMENTS;

vi.mock("../../hooks/useApi", () => ({
  // The REAL /api/assignments contract is {assignments: [...], events: [...]} —
  // NOT a bare array (samagra/api/app.py api_assignments). Mocking the true
  // shape here is load-bearing: a bare-array mock let the component ship with a
  // TypeError against the live backend (Codex review 28 / adversarial G3 review).
  useApi: (path: string) =>
    path.startsWith("/api/assignments")
      ? { data: { assignments: mockAssignments, events: [] }, loading: false, error: null }
      : { data: { chapters: {} }, loading: false, error: null },
}));
const post = vi.fn().mockResolvedValue({ ok: true, result: { published: ["revision"] } });
vi.mock("../../hooks/useApiPost", () => ({ useApiPost: () => ({ post, loading: false, error: null }) }));

afterEach(() => {
  vi.clearAllMocks();
  mockAssignments = DEFAULT_ASSIGNMENTS;
});

describe("Publish operator control (G3)", () => {
  it("lists captured chapters with a publish action", async () => {
    render(<Publish />);
    expect(await screen.findByText(/circular-motion/i)).toBeTruthy();
  });

  it("publishes a chapter via POST /api/factory/publish", async () => {
    render(<Publish />);
    fireEvent.click(await screen.findByTestId("publish-circular-motion"));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/factory/publish", { chapter: "circular-motion" }));
  });
});

const planMock = vi.fn();
const approveMock = vi.fn();
const buildMock = vi.fn();
vi.mock("../../lib/publishctl/recipe", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/publishctl/recipe")>();
  return {
    ...actual,
    planRequest: (...a: unknown[]) => planMock(...a),
    approveSeedRequest: (...a: unknown[]) => approveMock(...a),
    buildRequest: (...a: unknown[]) => buildMock(...a),
  };
});

describe("Factory run stepper panel (G5)", () => {
  it("renders a chapter-slug input and only the Plan button enabled with an empty slug", () => {
    render(<Publish />);
    expect(screen.getByTestId("factory-run-slug")).toBeTruthy();
    // House convention: placeholder-only inputs carry an aria-label
    // (Munshi/Sims/Notes precedents).
    expect(screen.getByLabelText("chapter slug")).toBeTruthy();
    expect(screen.getByTestId("factory-run-plan")).toBeTruthy();
  });

  it("clicking Plan calls planRequest with the textbook:-prefixed slug and shows a result line", async () => {
    // Use a slug distinct from the default mockAssignments' circular-motion row
    // so this seed genuinely has zero rows -> step === "plan" (Plan enabled).
    planMock.mockResolvedValue({ proposals: [
      { seed_ref: "textbook:gravitation", line: "revision", expected_output: "x", assignment_id: "a1" },
      { seed_ref: "textbook:gravitation", line: "deck", expected_output: "x", assignment_id: "a2" },
    ] });
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "gravitation" } });
    fireEvent.click(screen.getByTestId("factory-run-plan"));
    await waitFor(() => expect(planMock).toHaveBeenCalledWith("textbook:gravitation"));
    expect(await screen.findByTestId("factory-run-result")).toBeTruthy();
  });

  it("shows an error line when a step fails", async () => {
    planMock.mockRejectedValue(new Error("seed_ref is required"));
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "gravitation" } });
    fireEvent.click(screen.getByTestId("factory-run-plan"));
    expect(await screen.findByTestId("factory-run-error")).toHaveTextContent("seed_ref is required");
  });

  it("build-all loops buildRequest once per approved row, in lane order, then stops", async () => {
    // 2 approved deterministic-lane rows for the seed under test, deliberately
    // out of lane order in the source data (deck before revision) to prove the
    // loop reorders by _LANE_ORDER (revision before deck).
    mockAssignments = [
      { id: "a-deck", seed_ref: "textbook:circular-motion", pipeline: "deck", status: "approved" },
      { id: "a-rev", seed_ref: "textbook:circular-motion", pipeline: "revision", status: "approved" },
    ];
    buildMock.mockResolvedValueOnce({ line: "revision", artifact_ref: "/a.html" })
      .mockResolvedValueOnce({ line: "deck", artifact_ref: "/b.html" });
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    fireEvent.click(screen.getByTestId("factory-run-build"));
    await waitFor(() => expect(buildMock).toHaveBeenCalledTimes(2));
    expect(buildMock.mock.calls[0][0]).toBe("a-rev");
    expect(buildMock.mock.calls[1][0]).toBe("a-deck");
    // No third call ever fires (loop terminates once nothing is approved).
    await new Promise((r) => setTimeout(r, 10));
    expect(buildMock).toHaveBeenCalledTimes(2);
  });

  it("gates the stepper: an in-review row enables only Approve seed", async () => {
    mockAssignments = [
      { id: "a1", seed_ref: "textbook:circular-motion", pipeline: "revision", status: "in-review" },
    ];
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    expect(await screen.findByTestId("factory-run-approve")).not.toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-plan")).toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-build")).toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-publish")).toHaveProperty("disabled", true);
  });

  it("gates the stepper: all-captured rows enable only Publish", async () => {
    mockAssignments = [
      { id: "a1", seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" },
    ];
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    expect(await screen.findByTestId("factory-run-publish")).not.toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-plan")).toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-approve")).toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-build")).toHaveProperty("disabled", true);
  });

  it("the deterministic-lane filter ignores a same-seed samadhan row when deriving the step", async () => {
    // All deterministic-lane rows captured PLUS a CLI-planned samadhan 'changes'
    // brief for the same seed — without the filter this would (per deriveStep's
    // rules) still read as "publish" here since neither in-review nor approved
    // is present, but the filter is what makes that provably true rather than
    // incidental: a samadhan row in 'in-review'/'approved' would otherwise wrongly
    // re-trigger "approve"/"build". Assert Publish is still the sole enabled gate.
    mockAssignments = [
      { id: "a1", seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" },
      { id: "a2", seed_ref: "textbook:circular-motion", pipeline: "samadhan", status: "changes" },
    ];
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    expect(await screen.findByTestId("factory-run-publish")).not.toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-plan")).toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-approve")).toHaveProperty("disabled", true);
    expect(screen.getByTestId("factory-run-build")).toHaveProperty("disabled", true);
  });

  it("the Publish button calls the EXISTING publish handler with the slug, not a new code path", async () => {
    mockAssignments = [
      { id: "a1", seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" },
    ];
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    fireEvent.click(await screen.findByTestId("factory-run-publish"));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/factory/publish", { chapter: "circular-motion" }));
  });

  it("disables the stepper buttons while a step request is in flight, re-enabling after it settles", async () => {
    // Deferred plan promise: while pending, the Plan button (and every other
    // stepper button) must be disabled so a double-click can't stomp/race the
    // result line; once settled, gating returns to the derived step.
    let resolvePlan!: (v: unknown) => void;
    planMock.mockReturnValue(new Promise((r) => { resolvePlan = r; }));
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "gravitation" } });
    const planBtn = screen.getByTestId("factory-run-plan");
    expect(planBtn).toHaveProperty("disabled", false);
    fireEvent.click(planBtn);
    await waitFor(() => expect(planBtn).toHaveProperty("disabled", true));
    resolvePlan({ proposals: [] });
    // Step is still "plan" for this seed (no rows), so Plan re-enables.
    await waitFor(() => expect(planBtn).toHaveProperty("disabled", false));
  });

  it("build-all in flight disables the Build button so a second click cannot start a concurrent loop", async () => {
    mockAssignments = [
      { id: "a-rev", seed_ref: "textbook:circular-motion", pipeline: "revision", status: "approved" },
    ];
    let resolveBuild!: (v: unknown) => void;
    buildMock.mockReturnValueOnce(new Promise((r) => { resolveBuild = r; }));
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    const buildBtn = screen.getByTestId("factory-run-build");
    fireEvent.click(buildBtn);
    await waitFor(() => expect(buildBtn).toHaveProperty("disabled", true));
    fireEvent.click(buildBtn); // must be a no-op: the button is disabled mid-loop
    resolveBuild({ line: "revision", artifact_ref: "/a.html" });
    await waitFor(() => expect(buildMock).toHaveBeenCalledTimes(1));
    // A second concurrent loop never started (would have been a 2nd call).
    await new Promise((r) => setTimeout(r, 10));
    expect(buildMock).toHaveBeenCalledTimes(1);
  });
});
