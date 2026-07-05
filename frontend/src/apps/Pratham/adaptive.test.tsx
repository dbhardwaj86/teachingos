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
vi.mock("../../lib/pratham/session", () => ({
  meRequest: (...a: unknown[]) => me(...a),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
}));
vi.mock("../../lib/pratham/plan", () => ({
  nextRequest: (...a: unknown[]) => next(...a),
  markDoneRequest: vi.fn(),
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
