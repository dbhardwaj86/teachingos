// frontend/src/apps/Publish/index.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Publish from "./index";

vi.mock("../../hooks/useApi", () => ({
  // The REAL /api/assignments contract is {assignments: [...], events: [...]} —
  // NOT a bare array (samagra/api/app.py api_assignments). Mocking the true
  // shape here is load-bearing: a bare-array mock let the component ship with a
  // TypeError against the live backend (Codex review 28 / adversarial G3 review).
  useApi: (path: string) =>
    path.startsWith("/api/assignments")
      ? { data: { assignments: [{ seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" }],
            events: [] },
          loading: false, error: null }
      : { data: { chapters: {} }, loading: false, error: null },
}));
const post = vi.fn().mockResolvedValue({ ok: true, result: { published: ["revision"] } });
vi.mock("../../hooks/useApiPost", () => ({ useApiPost: () => ({ post, loading: false, error: null }) }));

afterEach(() => vi.clearAllMocks());

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
