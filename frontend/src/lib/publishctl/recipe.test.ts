// frontend/src/lib/publishctl/recipe.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveSeedRequest, buildRequest, deriveStep, isDeterministicLane, nextAssignmentToBuild,
  planRequest, type AssignmentLike,
} from "./recipe";

const ok = (body: unknown) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
const bad = (code: number, detail = "boom") =>
  Promise.resolve({
    ok: false, status: code, json: () => Promise.resolve({ detail }),
  } as Response);

afterEach(() => vi.unstubAllGlobals());

describe("deriveStep (G5 stepper state)", () => {
  it("is 'plan' when there are no assignments for this seed yet", () => {
    expect(deriveStep([])).toBe("plan");
  });

  it("is 'plan' when handed null (defensive contract)", () => {
    expect(deriveStep(null)).toBe("plan");
  });

  it("is 'plan' when handed undefined (defensive contract)", () => {
    expect(deriveStep(undefined)).toBe("plan");
  });

  it("is 'approve' when any row is in-review", () => {
    const rows: AssignmentLike[] = [
      { id: "a1", pipeline: "revision", status: "in-review" },
      { id: "a2", pipeline: "deck", status: "approved" },
    ];
    expect(deriveStep(rows)).toBe("approve");
  });

  it("is 'build' when nothing is in-review but something is approved", () => {
    const rows: AssignmentLike[] = [
      { id: "a1", pipeline: "revision", status: "approved" },
      { id: "a2", pipeline: "deck", status: "captured" },
    ];
    expect(deriveStep(rows)).toBe("build");
  });

  it("is 'publish' when every row is terminal captured", () => {
    const rows: AssignmentLike[] = [
      { id: "a1", pipeline: "revision", status: "captured" },
      { id: "a2", pipeline: "deck", status: "captured" },
    ];
    expect(deriveStep(rows)).toBe("publish");
  });
});

describe("nextAssignmentToBuild", () => {
  it("returns the first approved row's id in lane order", () => {
    const rows: AssignmentLike[] = [
      { id: "a-deck", pipeline: "deck", status: "approved" },
      { id: "a-rev", pipeline: "revision", status: "approved" },
    ];
    // lane order: revision before deck
    expect(nextAssignmentToBuild(rows)).toBe("a-rev");
  });

  it("returns null when nothing is approved", () => {
    expect(nextAssignmentToBuild([{ id: "a1", pipeline: "revision", status: "captured" }]))
      .toBeNull();
  });

  it("returns null when handed null (defensive contract)", () => {
    expect(nextAssignmentToBuild(null)).toBeNull();
  });
});

describe("isDeterministicLane", () => {
  it("is true for each of the 5 deterministic lanes", () => {
    expect(isDeterministicLane("revision")).toBe(true);
    expect(isDeterministicLane("lecture")).toBe(true);
    expect(isDeterministicLane("deck")).toBe(true);
    expect(isDeterministicLane("paper")).toBe(true);
    expect(isDeterministicLane("drill")).toBe(true);
  });

  it("is false for the llm/mcd lanes and for undefined", () => {
    expect(isDeterministicLane("samadhan")).toBe(false);
    expect(isDeterministicLane("seed")).toBe(false);
    expect(isDeterministicLane(undefined)).toBe(false);
  });
});

describe("fetch wrappers", () => {
  it("planRequest posts seed_ref and returns proposals", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ proposals: [{ line: "revision" }] }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await planRequest("textbook:circular-motion");
    expect(res).toEqual({ proposals: [{ line: "revision" }] });
    expect(fetchMock).toHaveBeenCalledWith("/api/factory/plan", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ seed_ref: "textbook:circular-motion" }),
    }));
  });

  it("planRequest throws the server detail on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(bad(400, "seed_ref is required")));
    await expect(planRequest("")).rejects.toThrow("seed_ref is required");
  });

  it("approveSeedRequest posts seed_ref and returns the approved list", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ seed_ref: "textbook:cm", approved: ["a1"] }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await approveSeedRequest("textbook:cm")).toEqual({ seed_ref: "textbook:cm", approved: ["a1"] });
    expect(fetchMock).toHaveBeenCalledWith("/api/factory/approve-seed", expect.objectContaining({
      method: "POST", body: JSON.stringify({ seed_ref: "textbook:cm" }),
    }));
  });

  it("buildRequest posts assignment_id and returns the build result", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ line: "revision", artifact_ref: "/x.html" }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await buildRequest("a1")).toEqual({ line: "revision", artifact_ref: "/x.html" });
    expect(fetchMock).toHaveBeenCalledWith("/api/factory/build", expect.objectContaining({
      method: "POST", body: JSON.stringify({ assignment_id: "a1" }),
    }));
  });

  it("buildRequest throws the server detail (e.g. a kind-refusal 403) on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(bad(403, "the mcd lane is CLI-only")));
    await expect(buildRequest("a1")).rejects.toThrow("the mcd lane is CLI-only");
  });
});
