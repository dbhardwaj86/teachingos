// src/shell/DesktopIcons.tsx — labeled, clickable desktop icon grid (Task 1).
// One tile per app in the frozen ORDER, each showing the FULL app name under an
// AppIcon accent tile (the StartMenu tile+caption precedent). Positions come from
// the pure lib/desktop/layout column-flow grid inside the theme workArea, so the
// grid clears the TopBar / Rail / Dock / Taskbar chrome in all three themes.
//
// F6 (BINDING): the full-bleed wrapper has pointerEvents:"none" while each tile is
// pointerEvents:"auto" — a right-click on empty desktop passes THROUGH the wrapper
// to the shell root, so App.tsx's `e.target === e.currentTarget` bare-desktop menu
// check still holds. Tile right-clicks stopPropagation and open the app menu.
// F9 (BINDING): a tile click first calls onDismiss (the shell's setMenu(null) +
// setStartOpen(false)) so an open context menu never floats past an icon click.
import type { AppId, Theme } from "../types/contracts";
import { APPS, ORDER } from "../registry";
import { THEMES } from "../themes";
import { iconPositions, CELL_W, CELL_H } from "../lib/desktop/layout";
import AppIcon from "../components/AppIcon";

export interface DesktopIconsProps {
  theme: Theme;
  vw: number;
  vh: number;
  /** Open-or-focus an app — wired to the WM store's `openApp`. */
  onOpen: (id: AppId) => void;
  /** Right-click → the dock-icon style app context menu. */
  onAppContextMenu: (id: AppId, x: number, y: number) => void;
  /** Dismiss any open context menu / start menu (F9). */
  onDismiss: () => void;
}

export default function DesktopIcons({
  theme,
  vw,
  vh,
  onOpen,
  onAppContextMenu,
  onDismiss,
}: DesktopIconsProps) {
  const t = THEMES[theme];
  const positions = iconPositions(theme, vw, vh, ORDER.length);

  return (
    <div
      data-testid="desktop-icons"
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 1, // behind every window (WindowFrame z starts higher)
        pointerEvents: "none", // F6 — bare-desktop right-click passes through
      }}
    >
      {ORDER.map((id, i) => {
        const app = APPS[id];
        const pos = positions[i];
        // samagra unifies tiles to the theme accent (dock/StartMenu convention).
        const accent = t.kind === "samagra" ? t.accent : app.accent;
        return (
          <div
            key={id}
            // NOT role="button": the dock/rail/taskbar launchers already own the
            // accessible button name per app; a second button with the same name
            // would make every getByRole("button", {name}) ambiguous. Tiles are
            // addressed by this stable testid (plan T1.2 note); the inner AppIcon
            // carries role="img" aria-label for AT.
            data-testid="desktop-tile"
            onClick={() => {
              onDismiss(); // F9 — clear any floating menu
              onOpen(id);
            }}
            onDoubleClick={() => {
              onDismiss();
              onOpen(id);
            }}
            onContextMenu={(e) => {
              e.preventDefault();
              e.stopPropagation(); // F6 — don't retrigger the bare-desktop menu
              onAppContextMenu(id, e.clientX, e.clientY);
            }}
            style={{
              position: "absolute",
              left: pos.x,
              top: pos.y,
              width: CELL_W,
              height: CELL_H,
              pointerEvents: "auto", // F6 — the tile itself IS interactive
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "flex-start",
              gap: 6,
              padding: "6px 2px",
              borderRadius: 10,
              cursor: "pointer",
              userSelect: "none",
              boxSizing: "border-box",
            }}
          >
            <AppIcon app={id} accent={accent} label={app.name} />
            <span
              data-testid="desktop-tile-caption"
              style={{
                fontSize: 10.5,
                lineHeight: 1.2,
                textAlign: "center",
                color: "var(--samagra-text)",
                maxWidth: CELL_W - 4,
                overflowWrap: "break-word",
              }}
            >
              {app.name}
            </span>
          </div>
        );
      })}
    </div>
  );
}
