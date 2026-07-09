// T3.2 — GN Brain corpus app: same-origin iframe of the gated serve proxy.
// Plan ruling F1: trusted gated owner app → NO sandbox attribute (the Pratham
// published-artifact sandbox precedent is a DIFFERENT, untouched case).
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import GnBrain from "./index";

const okFetch = () => Promise.resolve({ ok: true } as Response);
const downFetch = () => Promise.reject(new Error("ECONNREFUSED"));

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(okFetch));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("GnBrain corpus app", () => {
  it("renders an iframe pointing at the corpus serve endpoint", async () => {
    render(<GnBrain />);
    await flush();
    const frame = screen.getByTitle("GN Brain") as HTMLIFrameElement;
    expect(frame.tagName).toBe("IFRAME");
    expect(frame.getAttribute("src")!.startsWith("/api/corpus/gnocr/serve/")).toBe(true);
    expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer");
    // F1: no sandbox attribute — same-origin trusted gated owner app.
    expect(frame.hasAttribute("sandbox")).toBe(false);
    // probed the gated status endpoint, not the serve proxy
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/corpus/gnocr");
  });

  it("fills and reflows with the window (no fixed px height)", async () => {
    render(<GnBrain />);
    await flush();
    const frame = screen.getByTitle("GN Brain") as HTMLIFrameElement;
    expect(frame.style.width).toBe("100%");
    expect(frame.style.height).toBe("100%");
    expect(frame.style.flex).toContain("1");
    // container is a filling flex column, no hardcoded px height anywhere
    const box = frame.parentElement as HTMLElement;
    expect(box.style.display).toBe("flex");
    expect(box.style.height).toBe("100%");
    expect(frame.style.height.endsWith("px")).toBe(false);
  });

  it("shows an offline fallback with Retry when the daemon is down", async () => {
    vi.stubGlobal("fetch", vi.fn(downFetch));
    render(<GnBrain />);
    await flush();
    expect(screen.getByText(/brain offline/i)).toBeInTheDocument();
    expect(screen.getByText(/:8931/)).toBeInTheDocument();
    expect(screen.queryByTitle("GN Brain")).toBeNull();
    // Retry re-probes and swaps the iframe back in when the daemon is up
    vi.stubGlobal("fetch", vi.fn(okFetch));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await flush();
    expect(screen.getByTitle("GN Brain")).toBeInTheDocument();
  });
});
