// frontend/src/apps/Pratham/adaptive.test.tsx
// G4 identity-optional invariant: an anonymous reader renders ZERO adaptive UI —
// written BEFORE the new JSX landed (spec §11) and kept green after it.
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Pratham from "./index";

const MAN = {
  version: "samagra.published.v1",
  chapters: {
    "circular-motion": {
      chapter: "circular-motion", title: "Circular Motion",
      artifacts: [{ lane: "revision", files: [{ ext: "html" }] }],
    },
  },
};

vi.mock("../../hooks/useApi", () => ({
  useApi: () => ({ data: MAN, loading: false, error: null }),
}));

const me = vi.fn();
const next = vi.fn();
const markDone = vi.fn();
vi.mock("../../lib/pratham/session", () => ({
  meRequest: (...a: unknown[]) => me(...a),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
}));
vi.mock("../../lib/pratham/plan", () => ({
  nextRequest: (...a: unknown[]) => next(...a),
  markDoneRequest: (...a: unknown[]) => markDone(...a),
}));

afterEach(() => vi.clearAllMocks());

describe("anonymous invariance (G4)", () => {
  it("renders no adaptive UI and never calls /api/learn/next when anonymous", async () => {
    me.mockResolvedValue(null);
    render(<Pratham />);
    await waitFor(() => expect(me).toHaveBeenCalled());
    expect(screen.queryByTestId("pratham-mark-done")).toBeNull();
    expect(screen.queryByTestId("pratham-next")).toBeNull();
    expect(screen.queryByTestId("pratham-done-badge")).toBeNull();
    expect(next).not.toHaveBeenCalled();
  });
});

describe("signed-in adaptive UI (G4)", () => {
  const PAYLOAD = {
    queue: [
      { chapter: "circular-motion", title: "Circular Motion", lane: "revision",
        reason: "high-demand", score: 700, rank: 1 },
    ],
    done: [],
  };

  it("renders the what's-next strip and a mark-done button when signed in", async () => {
    me.mockResolvedValue({ id: "stu_1", name: "Asha" });
    next.mockResolvedValue(PAYLOAD);
    render(<Pratham />);
    expect(await screen.findByTestId("pratham-next")).toBeTruthy();
    expect(await screen.findByTestId("pratham-mark-done")).toBeTruthy();
  });

  it("marking done POSTs the current pair and refetches the queue", async () => {
    me.mockResolvedValue({ id: "stu_1", name: "Asha" });
    next.mockResolvedValue(PAYLOAD);
    markDone.mockResolvedValue(true);
    render(<Pratham />);
    (await screen.findByTestId("pratham-mark-done")).click();
    await waitFor(() => {
      expect(markDone).toHaveBeenCalledWith("circular-motion", "revision");
      expect(next.mock.calls.length).toBeGreaterThanOrEqual(2);   // initial + refetch
    });
  });

  it("shows the done badge instead of the button for an already-done pair", async () => {
    me.mockResolvedValue({ id: "stu_1", name: "Asha" });
    next.mockResolvedValue({ queue: [], done: [
      { chapter: "circular-motion", lane: "revision", status: "done",
        marked_at: "2026-07-05T10:00:00Z" }] });
    render(<Pratham />);
    expect(await screen.findByTestId("pratham-done-badge")).toBeTruthy();
    expect(screen.queryByTestId("pratham-mark-done")).toBeNull();
  });
});
