// T1.1 — pure desktop-icon grid layout math (ZERO DOM).
// Icons flow down a vertical column inside the theme's workArea insets, wrap to
// the next column, and CLAMP within the work area on overflow (F10 — never scroll).
import { describe, it, expect } from "vitest";
import { iconPositions, CELL_W, CELL_H, GAP } from "./layout";
import { workArea } from "../wm/geometry";
import type { Theme } from "../../types/contracts";

const THEMES: Theme[] = ["aqua", "console", "samagra"];

describe("iconPositions", () => {
  it("places the first icon at the theme work-area top-left inset", () => {
    for (const theme of THEMES) {
      const wa = workArea(theme, 1440, 900);
      const [first] = iconPositions(theme, 1440, 900, 5);
      expect(first.x).toBeGreaterThanOrEqual(wa.x);
      expect(first.y).toBeGreaterThanOrEqual(wa.y);
      // top-left: the first icon sits AT the inset, not merely after it
      expect(first).toEqual({ x: wa.x, y: wa.y });
    }
  });

  it("lays out a vertical column then wraps to the next column", () => {
    const wa = workArea("aqua", 1440, 900);
    const rows = Math.floor((wa.h + GAP) / (CELL_H + GAP));
    const pos = iconPositions("aqua", 1440, 900, rows + 2);
    // first `rows` icons share the first column x, descending y
    for (let i = 0; i < rows; i++) {
      expect(pos[i].x).toBe(wa.x);
      expect(pos[i].y).toBe(wa.y + i * (CELL_H + GAP));
    }
    // the next icon wraps to the second column, back at the top
    expect(pos[rows].x).toBe(wa.x + CELL_W + GAP);
    expect(pos[rows].y).toBe(wa.y);
  });

  it("clamps overflow icons within the work area and never scrolls", () => {
    // F10 — a count exceeding grid capacity must clamp, not exit the work area.
    for (const theme of THEMES) {
      const wa = workArea(theme, 800, 500);
      const pos = iconPositions(theme, 800, 500, 500);
      expect(pos).toHaveLength(500);
      for (const p of pos) {
        expect(p.x).toBeGreaterThanOrEqual(wa.x);
        expect(p.y).toBeGreaterThanOrEqual(wa.y);
        expect(p.x + CELL_W).toBeLessThanOrEqual(wa.x + wa.w);
        expect(p.y + CELL_H).toBeLessThanOrEqual(wa.y + wa.h);
      }
    }
  });

  it("shifts the whole grid clear of the samagra rail", () => {
    const wa = workArea("samagra", 1440, 900);
    const pos = iconPositions("samagra", 1440, 900, 19);
    // samagra workArea starts at rail+8 — every icon must be at/after it
    for (const p of pos) expect(p.x).toBeGreaterThanOrEqual(wa.x);
    expect(wa.x).toBeGreaterThan(8); // sanity: the rail inset is real
  });

  it("returns [] for count 0", () => {
    expect(iconPositions("aqua", 1440, 900, 0)).toEqual([]);
  });
});
