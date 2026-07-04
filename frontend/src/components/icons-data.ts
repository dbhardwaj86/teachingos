// src/components/icons-data.ts — FD2 ICON DATA (proto.md / .dc.html ICONS map).
// Each value is the EXACT path-data string from the prototype's `ICONS` object
// (.dc.html lines ~96-114), copied VERBATIM. Multi-segment glyphs separate their
// sub-paths with `|`; the <Icon> component splits on `|` into one <path> each.
// 24×24 viewBox, stroke 1.9, round caps/joins, fill none — see Icon.tsx.
// DATA ONLY; do not edit path strings — they are the authoritative source of truth.
import type { AppId } from "../types/contracts";

/** Raw 24×24 line-icon path data, keyed by app id. Verbatim from the prototype. */
export const ICONS: Record<AppId, string> = {
  dashboard: "M3 3h7v7H3z|M14 3h7v7h-7z|M14 14h7v7h-7z|M3 14h7v7H3z",
  terminal:
    "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z|M7 9l3 3-3 3|M13 15h4",
  questions:
    "M9.1 9a3 3 0 1 1 4.5 2.6c-.9.5-1.6 1.2-1.6 2.4|M12 17h.01|M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  lectures:
    "M4 19.5A2.5 2.5 0 0 1 6.5 17H20|M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z",
  booklets: "M12 2 2 7l10 5 10-5-10-5z|M2 17l10 5 10-5|M2 12l10 5 10-5",
  insp: "M12 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12z|M8.2 13.9 7 22l5-3 5 3-1.2-8.1",
  sims:
    "M12 10.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3|M12 3c5 0 9 4 9 9|M21 12c0 5-4 9-9 9|M12 21c-5 0-9-4-9-9|M3 12c0-5 4-9 9-9|M5 5c5 5 9 9 14 14|M19 5C14 10 10 14 5 19",
  pipelines: "M2 12h4l3 8 4-16 3 8h6",
  assignments:
    "M9 11l3 3L22 4|M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  org: "M9 3h6v4H9z|M3 17h6v4H3z|M15 17h6v4h-6z|M12 7v4|M6 17v-2h12v2",
  munshi:
    "M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z|M19 10a7 7 0 0 1-14 0|M12 19v3|M8 22h8",
  mycontentdev:
    "M7 20h10|M12 20V9|M12 9a4 4 0 0 1 4-4 4 4 0 0 1-4 4z|M12 12a4 4 0 0 0-4-4 4 4 0 0 0 4 4z",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z|M12 7v5l3 2",
  snake:
    "M17.32 5H6.68a4 4 0 0 0-3.98 3.59C2.6 9.4 2 14.46 2 16a3 3 0 0 0 5 2l1.4-1.4a2 2 0 0 1 1.43-.6h4.34a2 2 0 0 1 1.43.6L17 18a3 3 0 0 0 5-2c0-1.54-.6-6.6-.7-7.41A4 4 0 0 0 17.32 5z|M8 11h2|M9 10v2|M15.5 10h.01|M18 12h.01",
  notes: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z|M14 2v6h6|M9 13h6|M9 17h4",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z|M19.4 13a7.9 7.9 0 0 0 .1-1 7.9 7.9 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a8 8 0 0 0-1.7-1L17 2h-4l-.3 2.6a8 8 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a8 8 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a8 8 0 0 0 1.7 1L13 22h-1l.3-2.6a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6z",
  atlas:
    "M3 6a2 2 0 1 0 4 0 2 2 0 0 0-4 0|M17 6a2 2 0 1 0 4 0 2 2 0 0 0-4 0|M3 18a2 2 0 1 0 4 0 2 2 0 0 0-4 0|M17 18a2 2 0 1 0 4 0 2 2 0 0 0-4 0|M7 6h10|M5 8l-1 8|M19 8l1 8|M7 18h10|M7.5 8l4.5 4 4.5-4",
  publish:
    "M12 3v11|M8 7l4-4 4 4|M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4",
};

/** Stroke width for the 24×24 line icons — verbatim from the prototype (`sw||1.9`). */
export const ICON_STROKE = 1.9;

/** Default render size (px) when none is supplied — verbatim from the prototype (`size||20`). */
export const ICON_DEFAULT_SIZE = 20;

/** Convert a `#rrggbb` hex to `rgba(r,g,b,a)`. Verbatim port of the prototype's `hex()`. */
export function hexA(c: string, a: number): string {
  const n = parseInt(c.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}
