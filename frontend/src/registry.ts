// src/registry.ts — DATA ONLY; frozen for E1
import type { AppId, AppMeta } from "./types/contracts";

export const APPS: Record<AppId, AppMeta> = {
  dashboard: { id: "dashboard", name: "Dashboard", accent: "#4f46e5", w: 940, h: 610 },
  pipelines: { id: "pipelines", name: "Pipelines", accent: "#db2777", w: 960, h: 600 },
  assignments: { id: "assignments", name: "Assignments", accent: "#0891b2", w: 1000, h: 630 },
  org: { id: "org", name: "Org Chart", accent: "#4338ca", w: 920, h: 640 },
  questions: { id: "questions", name: "Questions", accent: "#2563eb", w: 900, h: 610 },
  lectures: { id: "lectures", name: "Lectures", accent: "#0d9488", w: 840, h: 600 },
  booklets: { id: "booklets", name: "Booklets", accent: "#b45309", w: 780, h: 560 },
  insp: { id: "insp", name: "INSP / Olympiad", accent: "#ca8a04", w: 800, h: 580 },
  sims: { id: "sims", name: "Simulations", accent: "#7c3aed", w: 880, h: 600 },
  mycontentdev: { id: "mycontentdev", name: "mycontentdev", accent: "#c026d3", w: 840, h: 610 },
  munshi: { id: "munshi", name: "Munshi", accent: "#059669", w: 430, h: 720 },
  activity: { id: "activity", name: "Activity", accent: "#ea580c", w: 480, h: 600 },
  settings: { id: "settings", name: "Settings", accent: "#475569", w: 760, h: 580 },
  terminal: { id: "terminal", name: "Terminal", accent: "#10b981", w: 740, h: 480 },
  clock: { id: "clock", name: "Clock", accent: "#0ea5e9", w: 560, h: 640 },
  notes: { id: "notes", name: "Notes", accent: "#f59e0b", w: 840, h: 600 },
  snake: { id: "snake", name: "Snake", accent: "#22c55e", w: 480, h: 680 },
  atlas: { id: "atlas", name: "Atlas", accent: "#06b6d4", w: 1040, h: 720 },
  publish: { id: "publish", name: "Publish", accent: "#16a34a", w: 900, h: 600 },
};

export const ORDER: AppId[] = [
  "dashboard", "pipelines", "assignments", "org", "questions", "lectures", "booklets",
  "insp", "sims", "mycontentdev", "munshi", "notes", "clock", "terminal", "snake",
  "activity", "settings", "atlas", "publish",
];

export const MOBILE_FAVORITES: AppId[] = ["dashboard", "notes", "clock", "munshi"];
