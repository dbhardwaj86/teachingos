// src/lib/desktop/layout.ts — pure desktop-icon grid layout math (ZERO DOM, T1.1).
// Icons flow COLUMN-MAJOR (down a vertical column, then wrap to the next column)
// inside the active theme's workArea insets (lib/wm/geometry) so they never overlap
// the TopBar / Rail / Dock / Taskbar chrome. On overflow (count > grid capacity)
// the later icons CLAMP to the last valid cell — the desktop NEVER scrolls (F10).
import type { Theme } from "../../types/contracts";
import { workArea } from "../wm/geometry";

/** Icon cell footprint — tile + caption + padding. */
export const CELL_W = 92;
export const CELL_H = 92;
/** Gap between cells, both axes. */
export const GAP = 10;

export interface IconPos {
  x: number;
  y: number;
}

/**
 * Compute the absolute `{x,y}` of `count` desktop icons for a theme + viewport.
 * Column-major flow from the work-area top-left; overflow clamps in-area (F10).
 */
export function iconPositions(
  theme: Theme,
  vw: number,
  vh: number,
  count: number,
): IconPos[] {
  if (count <= 0) return [];
  const wa = workArea(theme, vw, vh);
  // Grid capacity — at least 1 row/col so a degenerate viewport still lays out.
  const rows = Math.max(1, Math.floor((wa.h + GAP) / (CELL_H + GAP)));
  const cols = Math.max(1, Math.floor((wa.w + GAP) / (CELL_W + GAP)));
  const out: IconPos[] = [];
  for (let i = 0; i < count; i++) {
    let col = Math.floor(i / rows);
    let row = i % rows;
    if (col >= cols) {
      // Overflow: clamp to the last valid cell — never paint outside / scroll.
      col = cols - 1;
      row = rows - 1;
    }
    // Final clamp keeps the whole cell inside the work area even on degenerate
    // viewports where a single cell exceeds the area.
    const x = Math.max(wa.x, Math.min(wa.x + col * (CELL_W + GAP), wa.x + wa.w - CELL_W));
    const y = Math.max(wa.y, Math.min(wa.y + row * (CELL_H + GAP), wa.y + wa.h - CELL_H));
    out.push({ x, y });
  }
  return out;
}
