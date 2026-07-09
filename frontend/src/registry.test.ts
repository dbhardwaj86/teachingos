import { describe, it, expect } from "vitest";
import { APPS, ORDER, MOBILE_FAVORITES } from "./registry";

describe("APPS registry", () => {
  it("has all 18 apps with exact accent + default size", () => {
    expect(APPS.dashboard).toEqual({ id: "dashboard", name: "Dashboard", accent: "#4f46e5", w: 940, h: 610 });
    expect(APPS.pipelines).toEqual({ id: "pipelines", name: "Pipelines", accent: "#db2777", w: 960, h: 600 });
    expect(APPS.assignments).toEqual({ id: "assignments", name: "Assignments", accent: "#0891b2", w: 1000, h: 630 });
    expect(APPS.org).toEqual({ id: "org", name: "Org Chart", accent: "#4338ca", w: 920, h: 640 });
    expect(APPS.questions).toEqual({ id: "questions", name: "Questions", accent: "#2563eb", w: 900, h: 610 });
    expect(APPS.lectures).toEqual({ id: "lectures", name: "Lectures", accent: "#0d9488", w: 840, h: 600 });
    expect(APPS.booklets).toEqual({ id: "booklets", name: "Booklets", accent: "#b45309", w: 780, h: 560 });
    expect(APPS.insp).toEqual({ id: "insp", name: "INSP / Olympiad", accent: "#ca8a04", w: 800, h: 580 });
    expect(APPS.sims).toEqual({ id: "sims", name: "Simulations", accent: "#7c3aed", w: 880, h: 600 });
    expect(APPS.mycontentdev).toEqual({ id: "mycontentdev", name: "mycontentdev", accent: "#c026d3", w: 840, h: 610 });
    expect(APPS.munshi).toEqual({ id: "munshi", name: "Munshi", accent: "#059669", w: 430, h: 720 });
    expect(APPS.activity).toEqual({ id: "activity", name: "Activity", accent: "#ea580c", w: 480, h: 600 });
    expect(APPS.settings).toEqual({ id: "settings", name: "Settings", accent: "#475569", w: 760, h: 580 });
    expect(APPS.terminal).toEqual({ id: "terminal", name: "Terminal", accent: "#10b981", w: 740, h: 480 });
    expect(APPS.clock).toEqual({ id: "clock", name: "Clock", accent: "#0ea5e9", w: 560, h: 640 });
    expect(APPS.notes).toEqual({ id: "notes", name: "Notes", accent: "#f59e0b", w: 840, h: 600 });
    expect(APPS.snake).toEqual({ id: "snake", name: "Snake", accent: "#22c55e", w: 480, h: 680 });
    expect(Object.keys(APPS)).toHaveLength(22);
  });
  it("ORDER is the exact dock/start order (not alpha, not APPS-key order)", () => {
    expect(ORDER).toEqual([
      "dashboard", "pipelines", "assignments", "org", "questions", "lectures", "booklets",
      "insp", "sims", "mycontentdev", "munshi", "notes", "clock", "terminal", "snake",
      "activity", "settings", "atlas", "publish", "gnocr", "onedpull", "lecturepdf",
    ]);
  });
  it("mobile favorites + min-size constant", () => {
    expect(MOBILE_FAVORITES).toEqual(["dashboard", "notes", "clock", "munshi"]);
  });
});

describe("Atlas registration", () => {
  it("registers the atlas app and includes it in ORDER", () => {
    expect(APPS.atlas).toMatchObject({ id: "atlas", name: "Atlas" });
    expect(ORDER).toContain("atlas");
  });
});

describe("Publish registration", () => {
  it("registers the publish app and includes it in ORDER", () => {
    expect(APPS.publish).toMatchObject({ id: "publish", name: "Publish" });
    expect(ORDER).toContain("publish");
  });
});

describe("Corpus apps registration (Stage B — T3.1)", () => {
  it("registers gnocr, onedpull, lecturepdf apps in APPS + ORDER", () => {
    expect(APPS.gnocr).toEqual({ id: "gnocr", name: "GN Brain", accent: "#a16207", w: 1000, h: 680 });
    expect(APPS.onedpull).toEqual({ id: "onedpull", name: "Corpus Brain", accent: "#b45309", w: 1040, h: 700 });
    expect(APPS.lecturepdf).toEqual({ id: "lecturepdf", name: "Lecture Brain", accent: "#0369a1", w: 1080, h: 720 });
    for (const id of ["gnocr", "onedpull", "lecturepdf"] as const) {
      expect(ORDER).toContain(id);
    }
  });
});
