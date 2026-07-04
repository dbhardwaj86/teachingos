// frontend/src/lib/publishctl/rows.test.ts
import { describe, expect, it } from "vitest";
import { publishRows } from "./rows";

const manifest = {
  chapters: {
    "circular-motion": {
      chapter: "circular-motion", title: "Circular Motion",
      artifacts: [{ lane: "revision" }],
    },
  },
};

const assignments = [
  { seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" },
  { seed_ref: "textbook:circular-motion", pipeline: "deck", status: "captured" },
  { seed_ref: "textbook:gravitation", pipeline: "revision", status: "captured" },
  { seed_ref: "textbook:gravitation", pipeline: "revision", status: "in-review" }, // not captured
  { seed_ref: "munshi:52", pipeline: "seed", status: "captured" },                 // not textbook
];

describe("publishRows", () => {
  it("merges captured textbook lanes with the published manifest", () => {
    const rows = publishRows(assignments, manifest);
    const cm = rows.find((r) => r.chapter === "circular-motion")!;
    expect(cm.title).toBe("Circular Motion");
    expect(cm.capturedLanes.sort()).toEqual(["deck", "revision"]);
    expect(cm.publishedLanes).toEqual(["revision"]);
  });

  it("includes captured chapters with nothing published yet", () => {
    const rows = publishRows(assignments, manifest);
    const grav = rows.find((r) => r.chapter === "gravitation")!;
    expect(grav.capturedLanes).toEqual(["revision"]);   // the in-review one is excluded
    expect(grav.publishedLanes).toEqual([]);
  });

  it("ignores non-textbook seeds and sorts by chapter", () => {
    const rows = publishRows(assignments, manifest);
    expect(rows.map((r) => r.chapter)).toEqual(["circular-motion", "gravitation"]);
  });

  it("is defensive against null inputs", () => {
    expect(publishRows(null, null)).toEqual([]);
  });

  it("degrades to no rows (never throws) when handed the raw {assignments,events} response object", () => {
    // Regression for review-28 / adversarial G3 review: the component once passed
    // the whole /api/assignments response object; that must not crash the render.
    const wholeResponse = { assignments, events: [] } as unknown as never;
    expect(publishRows(wholeResponse, manifest)).toEqual([]);
  });
});
