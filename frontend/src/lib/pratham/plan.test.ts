// frontend/src/lib/pratham/plan.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { markDoneRequest, nextRequest } from "./plan";

const ok = (body: unknown) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
const status = (code: number) =>
  Promise.resolve({ ok: false, status: code, json: () => Promise.resolve({}) } as Response);

afterEach(() => vi.unstubAllGlobals());

describe("plan.ts wrappers (G4)", () => {
  it("nextRequest returns the payload with same-origin credentials", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ queue: [], done: [] }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await nextRequest()).toEqual({ queue: [], done: [] });
    expect(fetchMock).toHaveBeenCalledWith("/api/learn/next",
      expect.objectContaining({ credentials: "same-origin" }));
  });

  it("nextRequest swallows 401/network to null (anonymous-safe)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(status(401)));
    expect(await nextRequest()).toBeNull();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("net")));
    expect(await nextRequest()).toBeNull();
  });

  it("markDoneRequest POSTs the pair and reports ok", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await markDoneRequest("circular-motion", "revision")).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/learn/progress",
      expect.objectContaining({
        method: "POST", credentials: "same-origin",
        body: JSON.stringify({ chapter: "circular-motion", lane: "revision" }),
      }));
  });

  it("markDoneRequest reports false on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(status(429)));
    expect(await markDoneRequest("c", "revision")).toBe(false);
  });
});
