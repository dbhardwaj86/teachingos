// CH1 fidelity — App shell assembly. Beyond the smoke render, these pin the
// shell-level fidelity wiring: the Aqua TopBar (with SAMAGRA wordmark + समग्र +
// live clock) and the bottom-center Dock are both mounted, every dock launcher is
// an inline <svg> app glyph (FD2 — never a letter badge), opening an app mounts a
// WindowFrame whose traffic-lights and title bar are present, and only the topmost
// window keeps its live traffic-light colors (the rest desaturate to #cdcdd4).
//
// CH2 fidelity (second describe block): switching the theme store to `console`
// swaps the chrome — the TopBar/Dock give way to the bottom Taskbar + Start menu,
// and every WindowFrame re-themes to the console right-side icon controls. These
// pin that theme-driven assembly (FD1) end-to-end through the real stores.
import { render, screen, fireEvent, act, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App, { wmStore, themeStore, APP_DIR } from "./App";
import { ORDER, APPS } from "./registry";
import { ICONS } from "./components/icons-data";
import { THEMES } from "./themes";

// Reset the shared WM store between tests so window assertions are isolated.
function resetWm() {
  act(() => {
    const s = wmStore.getState();
    s.windows.slice().forEach((w) => s.closeApp(w.id));
  });
}

// Reset the shared theme store back to aqua (the E1 default) between CH2 tests so
// the CH1 aqua block stays isolated regardless of test ordering.
function resetTheme() {
  act(() => themeStore.getState().setTheme("aqua"));
}

describe("App (CH1 aqua chrome fidelity)", () => {
  it("renders the shell root element", () => {
    const { container } = render(<App />);
    expect(container.querySelector("#samagra-os-shell")).toBeInTheDocument();
    resetWm();
  });

  it("sets the theme --samagra-* CSS vars on the shell root so var() resolves app-wide", () => {
    // Without these, every var(--samagra-*) falls back app-wide — most apps tolerate
    // it (transparent bg + black text ≈ aqua) but the Clock face SVG fill defaults to
    // a solid BLACK disc. The shell root must expose the active theme's tokens as vars.
    const { container } = render(<App />);
    const shell = container.querySelector("#samagra-os-shell") as HTMLElement;
    expect(shell.style.getPropertyValue("--samagra-card-bg")).toBe(THEMES.aqua.cardBg);
    expect(shell.style.getPropertyValue("--samagra-accent")).toBe(THEMES.aqua.accent);
    expect(shell.style.getPropertyValue("--samagra-text")).toBe(THEMES.aqua.text);
    resetWm();
  });

  it("mounts the Aqua TopBar with the SAMAGRA + समग्र wordmarks and a live clock", () => {
    render(<App />);
    expect(screen.getByText("SAMAGRA")).toBeInTheDocument();
    expect(screen.getByText("समग्र")).toBeInTheDocument();
    // the live clock is a 12-hour AM/PM string
    expect(screen.getByText(/\d{1,2}:\d{2}\s(AM|PM)/)).toBeInTheDocument();
    resetWm();
  });

  it("mounts the Dock with one inline <svg> launcher per app (no letter badges)", () => {
    render(<App />);
    const dock = screen.getByRole("toolbar", { name: /dock/i });
    expect(dock.querySelectorAll("svg")).toHaveLength(ORDER.length);
    // first launcher is an icon tile, not a text glyph
    const dash = screen.getByRole("button", { name: /dashboard/i });
    expect(dash.textContent).toBe("");
    resetWm();
  });

  it("opens a window with traffic-lights + centered title when a dock app is clicked", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));
    // a dialog window frame appears with the app title + left traffic lights
    expect(screen.getByRole("dialog", { name: "Terminal" })).toBeInTheDocument();
    expect(screen.getByLabelText("Close")).toBeInTheDocument();
    expect(screen.getByLabelText("Minimize")).toBeInTheDocument();
    expect(screen.getByLabelText("Maximize")).toBeInTheDocument();
    resetWm();
  });

  it("keeps live traffic-lights only on the topmost window; older windows desaturate", () => {
    render(<App />);
    // open two windows — the second is on top (active), the first goes inactive
    fireEvent.click(screen.getByRole("button", { name: /dashboard/i }));
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));

    const dashWin = screen.getByRole("dialog", { name: "Dashboard" });
    const termWin = screen.getByRole("dialog", { name: "Terminal" });

    const dashClose = dashWin.querySelector('[aria-label="Close"]') as HTMLElement;
    const termClose = termWin.querySelector('[aria-label="Close"]') as HTMLElement;

    // Terminal is on top → live red; Dashboard is behind → desaturated grey.
    expect(termClose.style.background).toBe("rgb(255, 95, 87)"); // #ff5f57 live
    expect(dashClose.style.background).toBe("rgb(205, 205, 212)"); // #cdcdd4 inactive
    resetWm();
  });
});

describe("App (CH2 console chrome assembly)", () => {
  it("swaps the Dock for the bottom Taskbar when the theme is console", () => {
    act(() => themeStore.getState().setTheme("console"));
    render(<App />);
    // the console chrome mounts the Taskbar (no top bar, no floating Dock)
    expect(screen.getByRole("toolbar", { name: /taskbar/i })).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: /dock/i })).toBeNull();
    // the Start button is present (its leading mark is an inline svg, FD2)
    const start = screen.getByRole("button", { name: /start/i });
    expect(start.querySelector("svg")).not.toBeNull();
    resetWm();
    resetTheme();
  });

  it("opens the Start menu from the taskbar and launches an app from it", () => {
    act(() => themeStore.getState().setTheme("console"));
    render(<App />);
    // Start menu is closed until the Start button is clicked
    expect(screen.queryByRole("menu", { name: /all apps/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /start/i }));
    expect(screen.getByRole("menu", { name: /all apps/i })).toBeInTheDocument();
    // launching Terminal from the menu opens its window
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));
    expect(screen.getByRole("dialog", { name: "Terminal" })).toBeInTheDocument();
    resetWm();
    resetTheme();
  });

  it("themes opened windows to the console right-side icon controls (no traffic dots)", () => {
    act(() => themeStore.getState().setTheme("console"));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /start/i }));
    fireEvent.click(screen.getByRole("button", { name: /dashboard/i }));
    const win = screen.getByRole("dialog", { name: "Dashboard" });
    const close = win.querySelector('[aria-label="Close"]') as HTMLElement;
    // console controls are 28×23 svg icon buttons, never 12×12 round traffic-lights
    expect(close.querySelector("svg")).not.toBeNull();
    expect(close.style.borderRadius).not.toBe("50%");
    resetWm();
    resetTheme();
  });

  it("surfaces a running-window button per open window on the taskbar", () => {
    act(() => themeStore.getState().setTheme("console"));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /start/i }));
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));
    const taskbar = screen.getByRole("toolbar", { name: /taskbar/i });
    const runningBtn = taskbar.querySelector('[data-testid="taskbar-window"]') as HTMLElement;
    expect(runningBtn).not.toBeNull();
    expect(runningBtn.textContent).toContain(APPS.terminal.name);
    resetWm();
    resetTheme();
  });
});

describe("App (CH3 samagra chrome assembly)", () => {
  it("mounts the left Rail (not the Dock or Taskbar) when the theme is samagra", () => {
    act(() => themeStore.getState().setTheme("samagra"));
    render(<App />);
    // samagra chrome mounts the left rail; no bottom-center Dock, no Taskbar
    const rail = screen.getByRole("toolbar", { name: /rail/i });
    expect(rail).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: /dock/i })).toBeNull();
    expect(screen.queryByRole("toolbar", { name: /taskbar/i })).toBeNull();
    // the rail leads with the स Devanagari wordmark tile
    expect(screen.getByText("स")).toBeInTheDocument();
    // one inline <svg> launcher per app (FD2 — no letter badges)
    expect(rail.querySelectorAll("svg").length).toBeGreaterThanOrEqual(ORDER.length);
    resetWm();
    resetTheme();
  });

  it("mounts the samagra TopBar with the समग्र Devanagari strip", () => {
    act(() => themeStore.getState().setTheme("samagra"));
    render(<App />);
    expect(screen.getByText("समग्र")).toBeInTheDocument();
    expect(screen.getByText("SAMAGRA · content OS")).toBeInTheDocument();
    resetWm();
    resetTheme();
  });

  it("opens a samagra window with right-side icon controls (no traffic-light dots)", () => {
    act(() => themeStore.getState().setTheme("samagra"));
    render(<App />);
    // launch Terminal from the rail
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));
    const winEl = screen.getByRole("dialog", { name: "Terminal" });
    const close = winEl.querySelector('[aria-label="Close"]') as HTMLElement;
    // samagra (controlSide right) uses 28×23 svg icon buttons, never 12×12 round dots
    expect(close.querySelector("svg")).not.toBeNull();
    expect(close.style.borderRadius).not.toBe("50%");
    expect(close.style.width).toBe("28px");
    resetWm();
    resetTheme();
  });

  it("shows the active left accent bar on a running rail launcher", () => {
    act(() => themeStore.getState().setTheme("samagra"));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));
    const term = screen.getByRole("button", { name: /terminal/i });
    expect(term.querySelector('[data-testid="rail-active-bar"]')).not.toBeNull();
    // a non-running app shows no bar
    const sims = screen.getByRole("button", { name: /simulations/i });
    expect(sims.querySelector('[data-testid="rail-active-bar"]')).toBeNull();
    resetWm();
    resetTheme();
  });
});

// Right-click context menus must work in ALL THREE themes (README §Context menus):
// a desktop menu on the bare background, a window menu on a title bar, and a
// dock-icon menu on a launcher — each driven by the same shell-owned menu state.
describe("App (right-click context menus — all themes)", () => {
  const shell = (c: HTMLElement) =>
    c.querySelector("#samagra-os-shell") as HTMLElement;

  it("opens the desktop menu on a bare-desktop right-click (aqua)", () => {
    const { container } = render(<App />);
    fireEvent.contextMenu(shell(container));
    // the documented desktop rows (README §Context menus — desktop)
    expect(screen.getByText("New Terminal")).toBeInTheDocument();
    expect(screen.getByText("Open Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Tile windows")).toBeInTheDocument();
    expect(screen.getByText("Close all windows")).toBeInTheDocument();
    // the Appearance theme-radio rows
    expect(screen.getByText("Aqua")).toBeInTheDocument();
    expect(screen.getByText("Console")).toBeInTheDocument();
    expect(screen.getByText("Samagra")).toBeInTheDocument();
    resetWm();
  });

  it("launches an app from the desktop menu (New Terminal)", () => {
    const { container } = render(<App />);
    fireEvent.contextMenu(shell(container));
    fireEvent.click(screen.getByText("New Terminal"));
    expect(screen.getByRole("dialog", { name: "Terminal" })).toBeInTheDocument();
    resetWm();
  });

  it("switches theme from the desktop menu Appearance radio", () => {
    const { container } = render(<App />);
    fireEvent.contextMenu(shell(container));
    fireEvent.click(screen.getByText("Console"));
    expect(themeStore.getState().theme).toBe("console");
    resetWm();
    resetTheme();
  });

  it("opens the desktop menu in the console theme too", () => {
    act(() => themeStore.getState().setTheme("console"));
    const { container } = render(<App />);
    fireEvent.contextMenu(shell(container));
    expect(screen.getByText("New Terminal")).toBeInTheDocument();
    expect(screen.getByText("Close all windows")).toBeInTheDocument();
    resetWm();
    resetTheme();
  });

  it("opens the desktop menu in the samagra theme too", () => {
    act(() => themeStore.getState().setTheme("samagra"));
    const { container } = render(<App />);
    fireEvent.contextMenu(shell(container));
    expect(screen.getByText("New Terminal")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    resetWm();
    resetTheme();
  });

  it("opens the window menu on a title-bar right-click (Bring to front + Close)", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /terminal/i }));
    const dialog = screen.getByRole("dialog", { name: "Terminal" });
    const titlebar = dialog.querySelector('[data-testid="titlebar"]') as HTMLElement;
    fireEvent.contextMenu(titlebar);
    expect(screen.getByText("Bring to front")).toBeInTheDocument();
    expect(screen.getByText("Minimize")).toBeInTheDocument();
    expect(screen.getByText("Close")).toBeInTheDocument();
    resetWm();
  });

  it("opens the dock-icon menu on an aqua dock right-click (Open + Close window)", () => {
    render(<App />);
    fireEvent.contextMenu(screen.getByRole("button", { name: /terminal/i }));
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("Close window")).toBeInTheDocument();
    resetWm();
  });

  it("opens the dock-icon menu on a samagra rail right-click", () => {
    act(() => themeStore.getState().setTheme("samagra"));
    render(<App />);
    fireEvent.contextMenu(screen.getByRole("button", { name: /terminal/i }));
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("Close window")).toBeInTheDocument();
    resetWm();
    resetTheme();
  });
});

// T1.3 — desktop icons: the labeled icon grid mounts on the bare desktop (PC only),
// opens apps through the real WM store, must NOT steal the bare-desktop right-click
// (F6 — the pointerEvents:none wrapper), and is absent in mobile device mode.
describe("App (desktop icons)", () => {
  const shell = (c: HTMLElement) =>
    c.querySelector("#samagra-os-shell") as HTMLElement;

  it("renders labeled desktop icons on the aqua desktop", () => {
    render(<App />);
    const grid = screen.getByTestId("desktop-icons");
    const tiles = within(grid).getAllByTestId("desktop-tile");
    expect(tiles).toHaveLength(ORDER.length);
    // a tile captioned with the FULL app name exists, outside any WindowFrame
    const dash = tiles.find((t) => t.textContent?.includes("Dashboard"));
    expect(dash).toBeTruthy();
    expect((dash as HTMLElement).closest('[role="dialog"]')).toBeNull();
    resetWm();
  });

  it("opens a window when a desktop icon is clicked", () => {
    render(<App />);
    const grid = screen.getByTestId("desktop-icons");
    const notes = within(grid)
      .getAllByTestId("desktop-tile")
      .find((t) => t.textContent?.includes("Notes")) as HTMLElement;
    fireEvent.click(notes);
    expect(screen.getByRole("dialog", { name: "Notes" })).toBeInTheDocument();
    resetWm();
  });

  it("still opens the desktop context menu on a bare-desktop right-click with DesktopIcons mounted", () => {
    // F6 regression — the wrapper must not become e.target on empty desktop.
    const { container } = render(<App />);
    fireEvent.contextMenu(shell(container));
    expect(screen.getByText("New Terminal")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    resetWm();
  });

  it("does NOT render desktop icons in mobile device mode", () => {
    act(() => themeStore.getState().setDevice("mobile"));
    render(<App />);
    expect(screen.queryByTestId("desktop-icons")).toBeNull();
    act(() => themeStore.getState().setDevice("pc"));
    resetWm();
  });

  it("renders desktop icons across all three themes", () => {
    for (const theme of ["aqua", "console", "samagra"] as const) {
      act(() => themeStore.getState().setTheme(theme));
      const { unmount } = render(<App />);
      const grid = screen.getByTestId("desktop-icons");
      expect(within(grid).getAllByTestId("desktop-tile")).toHaveLength(ORDER.length);
      // click an icon → its window mounts ABOVE the grid (higher z than wrapper z=1)
      const term = within(grid)
        .getAllByTestId("desktop-tile")
        .find((t) => t.textContent?.includes("Terminal")) as HTMLElement;
      fireEvent.click(term);
      const win = screen.getByRole("dialog", { name: "Terminal" });
      expect(Number((win as HTMLElement).style.zIndex)).toBeGreaterThan(1);
      resetWm();
      unmount();
    }
    resetTheme();
  });
});

// E3 — switching the device store to `mobile` swaps the whole desktop shell for
// the phone frame; opening an app shows it full-screen and Home returns to the
// grid. Pins the device-driven assembly end-to-end through the real stores.
describe("App (E3 mobile device mode)", () => {
  // setDevice('pc') also clears mobileApp (proto §1.11) — restores the desktop.
  const resetDevice = () => act(() => themeStore.getState().setDevice("pc"));

  it("swaps the aqua Dock for the phone frame when device is mobile", () => {
    act(() => themeStore.getState().setDevice("mobile"));
    render(<App />);
    expect(screen.getByTestId("mobile-frame")).toBeInTheDocument();
    // The aqua Dock is the chrome mounted at aqua/pc; it must disappear in mobile.
    expect(screen.queryByRole("toolbar", { name: /dock/i })).toBeNull();
    resetDevice();
    resetWm();
  });

  it("device beats theme chrome — mobile frame replaces the console Taskbar", () => {
    // Genuine guard: the Taskbar is console-only chrome, so flipping device to
    // mobile WHILE the theme is console proves the device branch wins over the
    // theme's desktop chrome (the Taskbar would otherwise be present).
    act(() => themeStore.getState().setTheme("console"));
    act(() => themeStore.getState().setDevice("mobile"));
    render(<App />);
    expect(screen.getByTestId("mobile-frame")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: /taskbar/i })).toBeNull();
    resetDevice();
    resetWm();
    resetTheme();
  });

  it("opens an app full-screen from the home grid and returns to the grid via Home", () => {
    act(() => themeStore.getState().setDevice("mobile"));
    render(<App />);
    expect(screen.getByTestId("mobile-grid")).toBeInTheDocument();
    // tap Notes in the home grid → full-screen app (the home grid disappears)
    fireEvent.click(
      within(screen.getByTestId("mobile-grid")).getByRole("button", { name: /notes/i }),
    );
    expect(screen.getByTestId("mobile-app")).toBeInTheDocument();
    expect(screen.queryByTestId("mobile-grid")).toBeNull();
    expect(themeStore.getState().mobileApp).toBe("notes");
    // tap Home → back to the grid
    fireEvent.click(screen.getByRole("button", { name: /home/i }));
    expect(screen.getByTestId("mobile-grid")).toBeInTheDocument();
    resetDevice();
    resetWm();
  });
});

// T3.1 — corpus apps registration (Stage B). ORDER-driven surfaces (Dock, Rail,
// StartMenu, Mobile, DesktopIcons) pick these up automatically via ORDER.
describe("corpus apps wiring (T3.1)", () => {
  it("registers gnocr, onedpull, lecturepdf apps", () => {
    for (const id of ["gnocr", "onedpull", "lecturepdf"] as const) {
      expect(APPS[id]).toBeTruthy();
      expect(ORDER).toContain(id);
      expect(ICONS[id]).toBeTruthy();
      expect(APP_DIR[id]).toBeTruthy();
    }
    expect(APP_DIR.gnocr).toBe("GnBrain");
    expect(APP_DIR.onedpull).toBe("CorpusBrain");
    expect(APP_DIR.lecturepdf).toBe("LectureBrain");
  });

  it("every ORDER id has an icon path", () => {
    for (const id of ORDER) {
      expect(ICONS[id], `ICONS["${id}"]`).toBeTruthy();
      expect(ICONS[id].trim().length).toBeGreaterThan(0);
    }
  });
});
