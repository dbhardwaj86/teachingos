// frontend/src/apps/Pratham/signin.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Pratham from "./index";

// The corpus fetch is irrelevant here — return an empty manifest so the reader
// mounts; we only exercise the additive sign-in affordance.
vi.mock("../../hooks/useApi", () => ({
  useApi: () => ({ data: { schema: "samagra.published.v1", chapters: {} }, loading: false, error: null }),
}));
vi.mock("../../lib/pratham/session", () => ({
  meRequest: vi.fn(),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
}));
import { loginRequest, logoutRequest, meRequest } from "../../lib/pratham/session";

afterEach(() => vi.clearAllMocks());

describe("Pratham sign-in (G3)", () => {
  it("shows a Sign in control when anonymous", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    render(<Pratham />);
    expect(await screen.findByTestId("pratham-signin")).toBeTruthy();
  });

  it("signs in with a code and shows the student name", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    (loginRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ student: { id: "s1", name: "Asha" } });
    render(<Pratham />);
    fireEvent.click(await screen.findByTestId("pratham-signin"));
    fireEvent.change(screen.getByTestId("pratham-signin-input"), { target: { value: "abc" } });
    fireEvent.click(screen.getByTestId("pratham-signin-submit"));
    await waitFor(() => expect(screen.getByTestId("pratham-user").textContent).toContain("Asha"));
    expect(loginRequest).toHaveBeenCalledWith("abc");
  });

  it("hydrates an already-signed-in student on mount", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "s1", name: "Ben" });
    render(<Pratham />);
    await waitFor(() => expect(screen.getByTestId("pratham-user").textContent).toContain("Ben"));
  });

  it("signs out", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "s1", name: "Ben" });
    (logoutRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true });
    render(<Pratham />);
    fireEvent.click(await screen.findByTestId("pratham-signout"));
    await waitFor(() => expect(screen.getByTestId("pratham-signin")).toBeTruthy());
  });

  it("shows an error on a bad code (login rejects)", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    (loginRequest as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("HTTP 401"));
    render(<Pratham />);
    fireEvent.click(await screen.findByTestId("pratham-signin"));
    fireEvent.change(screen.getByTestId("pratham-signin-input"), { target: { value: "bad" } });
    fireEvent.click(screen.getByTestId("pratham-signin-submit"));
    expect(await screen.findByTestId("pratham-signin-error")).toBeTruthy();
  });
});
