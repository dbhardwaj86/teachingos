// frontend/src/lib/pratham/session.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { loginRequest, logoutRequest, meRequest } from "./session";

afterEach(() => vi.restoreAllMocks());

function mockFetch(ok: boolean, body: unknown) {
  return vi.fn(async () => ({ ok, json: async () => body })) as unknown as typeof fetch;
}

describe("pratham session wrappers", () => {
  it("loginRequest posts the code and returns the student", async () => {
    const f = mockFetch(true, { student: { id: "stu_1", name: "Asha" } });
    vi.stubGlobal("fetch", f);
    const r = await loginRequest("abc");
    expect(r.student.name).toBe("Asha");
    const [url, opts] = (f as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/learn/login");
    expect(JSON.parse((opts as RequestInit).body as string)).toEqual({ code: "abc" });
  });

  it("loginRequest throws on a non-2xx (so the caller can show an error)", async () => {
    vi.stubGlobal("fetch", mockFetch(false, { detail: "invalid code" }));
    await expect(loginRequest("bad")).rejects.toThrow();
  });

  it("meRequest returns the student when present", async () => {
    vi.stubGlobal("fetch", mockFetch(true, { student: { id: "stu_1", name: "Asha" } }));
    expect(await meRequest()).toEqual({ id: "stu_1", name: "Asha" });
  });

  it("meRequest returns null when not authenticated / on error", async () => {
    vi.stubGlobal("fetch", mockFetch(true, { student: null }));
    expect(await meRequest()).toBeNull();
    vi.stubGlobal("fetch", mockFetch(false, {}));
    expect(await meRequest()).toBeNull();
  });

  it("logoutRequest posts to the logout endpoint", async () => {
    const f = mockFetch(true, { ok: true });
    vi.stubGlobal("fetch", f);
    await logoutRequest();
    expect((f as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe("/api/learn/logout");
    const opts = (f as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect((opts as RequestInit).method).toBe("POST");
  });

  it("logoutRequest throws on a non-2xx", async () => {
    vi.stubGlobal("fetch", mockFetch(false, {}));
    await expect(logoutRequest()).rejects.toThrow();
  });

  it("meRequest returns null when fetch itself rejects (offline)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch);
    expect(await meRequest()).toBeNull();
  });
});
