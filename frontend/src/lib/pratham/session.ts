// frontend/src/lib/pratham/session.ts
// Thin fetch wrappers for the PUBLIC /api/learn/* identity endpoints (Phase G3).
// The reader manages signed-in state from these; anonymous reading needs none.
import type { Student } from "../../types/contracts";

export interface MeResponse { student: Student | null; }
export interface LoginResponse { student: Student; }

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function loginRequest(code: string): Promise<LoginResponse> {
  return postJson<LoginResponse>("/api/learn/login", { code });
}

export function logoutRequest(): Promise<{ ok: true }> {
  return postJson<{ ok: true }>("/api/learn/logout", {});
}

export async function meRequest(): Promise<Student | null> {
  try {
    const res = await fetch("/api/learn/me", { headers: { accept: "application/json" }, credentials: "same-origin" });
    if (!res.ok) return null;
    const j = (await res.json()) as MeResponse;
    return j.student ?? null;
  } catch {
    return null;
  }
}
