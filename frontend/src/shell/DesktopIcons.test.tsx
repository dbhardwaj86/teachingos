// T1.2 — DesktopIcons: labeled clickable icon grid on the bare desktop.
// Pins the F6 ruling (pointerEvents:"none" wrapper + per-tile "auto" so a
// bare-desktop right-click passes THROUGH to the shell root) and the F9 ruling
// (a tile click dismisses any open context menu via the explicit onDismiss prop).
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import DesktopIcons from "./DesktopIcons";
import { APPS, ORDER } from "../registry";
import type { Theme } from "../types/contracts";

function renderIcons(theme: Theme = "aqua") {
  const onOpen = vi.fn();
  const onAppContextMenu = vi.fn();
  const onDismiss = vi.fn();
  const parentContextMenu = vi.fn();
  const utils = render(
    <div onContextMenu={parentContextMenu}>
      <DesktopIcons
        theme={theme}
        vw={1440}
        vh={900}
        onOpen={onOpen}
        onAppContextMenu={onAppContextMenu}
        onDismiss={onDismiss}
      />
    </div>,
  );
  return { onOpen, onAppContextMenu, onDismiss, parentContextMenu, ...utils };
}

const tileFor = (name: string) => {
  const tiles = screen.getAllByTestId("desktop-tile");
  const tile = tiles.find((t) => t.textContent?.includes(name));
  expect(tile).toBeTruthy();
  return tile as HTMLElement;
};

describe("DesktopIcons", () => {
  it("renders one labeled tile per app in ORDER", () => {
    renderIcons();
    const tiles = screen.getAllByTestId("desktop-tile");
    expect(tiles).toHaveLength(ORDER.length);
    // every app's full name is visible as caption text
    for (const id of ORDER) {
      expect(
        tiles.some((t) => t.textContent?.includes(APPS[id].name)),
      ).toBe(true);
    }
  });

  it("calls onOpen with the app id on click", () => {
    const { onOpen } = renderIcons();
    fireEvent.click(tileFor("Dashboard"));
    expect(onOpen).toHaveBeenCalledWith("dashboard");
  });

  it("also opens on double-click", () => {
    const { onOpen } = renderIcons();
    fireEvent.doubleClick(tileFor("Notes"));
    expect(onOpen).toHaveBeenCalledWith("notes");
  });

  it("dismisses open menus on click", () => {
    // F9 — a tile click must clear any floating context menu / start menu.
    const { onDismiss } = renderIcons();
    fireEvent.click(tileFor("Dashboard"));
    expect(onDismiss).toHaveBeenCalled();
  });

  it("opens the app context menu on right-click with stopPropagation", () => {
    // F6 — the right-click opens the app menu and does NOT bubble to a parent
    // (which would re-trigger the bare-desktop menu).
    const { onAppContextMenu, parentContextMenu } = renderIcons();
    fireEvent.contextMenu(tileFor("Dashboard"), { clientX: 120, clientY: 200 });
    expect(onAppContextMenu).toHaveBeenCalledWith("dashboard", 120, 200);
    expect(parentContextMenu).not.toHaveBeenCalled();
  });

  it("lets a bare-wrapper right-click pass through (pointerEvents none)", () => {
    // F6 — wrapper pointerEvents:"none", each tile pointerEvents:"auto".
    renderIcons();
    const wrapper = screen.getByTestId("desktop-icons");
    expect(wrapper.style.pointerEvents).toBe("none");
    for (const tile of screen.getAllByTestId("desktop-tile")) {
      expect(tile.style.pointerEvents).toBe("auto");
    }
  });

  it("paints captions with the theme text token", () => {
    for (const theme of ["aqua", "console", "samagra"] as Theme[]) {
      const { unmount } = renderIcons(theme);
      const captions = screen.getAllByTestId("desktop-tile-caption");
      expect(captions.length).toBe(ORDER.length);
      for (const c of captions) {
        expect(c.style.color).toBe("var(--samagra-text)");
      }
      unmount();
    }
  });
});
