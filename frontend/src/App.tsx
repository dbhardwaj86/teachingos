// src/App.tsx — SAMAGRA OS shell assembly (E1.18 + CH2 console chrome).
// Assembles the per-theme chrome over the WM + theme stores. The chrome that wraps
// the windows is theme-driven (FD1):
//   - aqua / samagra (`kind!=='console'`): a top bar (TopBar) + a bottom-center /
//     left-rail Dock.
//   - console (`kind==='console'`): NO top bar — a bottom Taskbar (Start button +
//     running-window strip + clock) with the Start-menu popover as its child.
// Every open window renders through one WindowFrame, themed to the active theme so
// its chrome (traffic-lights vs right-side icon controls, radius, glow ring) matches.
// This is a THIN shell — all window math lives in lib/wm/* (via the WM store) and all
// theme tokens in themes/.
//
// Right-click context menus (README §Context menus) work in ALL THREE themes. The
// shell owns one menu whose items depend on WHERE the right-click landed:
//   - desktop (bare shell background): New Terminal · Open Dashboard · Appearance
//     (theme radio) · Tile windows · Switch device · Close all windows.
//   - window title bar (any theme): Bring to front · Maximize/Restore · Minimize · Close.
//   - dock / rail icon: Open · Close window.
// The console taskbar's running-window buttons reuse the window menu. The menu surface
// itself is theme-driven (ContextMenu reads the active theme tokens) so it is correct
// under aqua / console / samagra.
//
// Cross-branch build invariant (division §1 †): open windows render ONLY through a
// runtime-resolved lazy import of `apps/<App>/index.tsx`. There is NO static import
// of any app module (including khanak-owned Clock/Notes/Snake), so this file
// compiles on agent/deepak before the leaf app files exist; each lazy import
// resolves only when a window of that app is actually opened at integration.
import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type CSSProperties,
} from "react";
import { useStore } from "zustand";
import type { AppId, Theme, WindowState } from "./types/contracts";
import { APPS } from "./registry";
import { getTheme, cssVars } from "./themes";
import { createWindowManagerStore } from "./stores/windowManager";
import { createThemeStore } from "./stores/theme";
import TopBar from "./shell/TopBar";
import Dock from "./shell/Dock";
import Rail from "./shell/Rail";
import Taskbar from "./shell/Taskbar";
import StartMenu from "./shell/StartMenu";
import WindowFrame from "./shell/WindowFrame";
import ContextMenu, { type ContextMenuItem } from "./shell/ContextMenu";
import Mobile from "./shell/Mobile";

// Wire the two stores once for the app lifetime (WM first, theme references it).
const wmStore = createWindowManagerStore();
const themeStore = createThemeStore({ wm: wmStore });

// Map an AppId to its `apps/<Dir>` folder. The dynamic import below is built from a
// VARIABLE specifier so the bundler does not statically resolve it at build time —
// this is what keeps App.tsx compilable before the leaf app files land.
const APP_DIR: Record<AppId, string> = {
  dashboard: "Dashboard",
  pipelines: "Pipelines",
  assignments: "Assignments",
  org: "Org",
  questions: "Questions",
  lectures: "Lectures",
  booklets: "Booklets",
  insp: "Insp",
  sims: "Sims",
  mycontentdev: "Mycontentdev",
  munshi: "Munshi",
  activity: "Activity",
  settings: "Settings",
  terminal: "Terminal",
  clock: "Clock",
  notes: "Notes",
  snake: "Snake",
  atlas: "Atlas",
  publish: "Publish",
};

// Appearance radio rows for the desktop menu (README §Context menus — theme checks).
const THEME_OPTIONS: ReadonlyArray<{ id: Theme; label: string }> = [
  { id: "aqua", label: "Aqua" },
  { id: "console", label: "Console" },
  { id: "samagra", label: "Samagra" },
];

const lazyCache = new Map<AppId, ComponentType>();

/** Lazy app component, resolved at render time (never at build time). */
function appComponent(id: AppId): ComponentType {
  const cached = lazyCache.get(id);
  if (cached) return cached;
  const dir = APP_DIR[id];
  const Comp = lazy(() =>
    import(`./apps/${dir}/index.tsx`).catch(() => ({
      default: () => null,
    })),
  ) as ComponentType;
  lazyCache.set(id, Comp);
  return Comp;
}

/** Format the live clock as the proto's `9:41 AM` 12-hour string. */
function fmtClock(d: Date): string {
  let h = d.getHours();
  const m = d.getMinutes();
  const ap = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${h}:${String(m).padStart(2, "0")} ${ap}`;
}

// The open context menu is one of three kinds, discriminated by where the right-click
// landed; `menuItems` builds the rows for the active kind (README §Context menus).
type MenuState =
  | { kind: "window"; winId: string; x: number; y: number }
  | { kind: "app"; appId: AppId; x: number; y: number }
  | { kind: "desktop"; x: number; y: number };

export default function App() {
  const windows = useStore(wmStore, (s) => s.windows);
  const openApp = useStore(wmStore, (s) => s.openApp);
  const closeApp = useStore(wmStore, (s) => s.closeApp);
  const minimize = useStore(wmStore, (s) => s.minimize);
  const toggleMax = useStore(wmStore, (s) => s.toggleMax);
  const focus = useStore(wmStore, (s) => s.focus);
  const move = useStore(wmStore, (s) => s.move);
  const resize = useStore(wmStore, (s) => s.resize);
  const tile = useStore(wmStore, (s) => s.tile);

  const theme = useStore(themeStore, (s) => s.theme);
  const device = useStore(themeStore, (s) => s.device);
  const mobileApp = useStore(themeStore, (s) => s.mobileApp);
  const setTheme = useStore(themeStore, (s) => s.setTheme);
  const setDevice = useStore(themeStore, (s) => s.setDevice);
  const openMobileApp = useStore(themeStore, (s) => s.openMobileApp);
  const goHome = useStore(themeStore, (s) => s.goHome);
  const t = getTheme(theme); // fallback-guarded index (advisory HIGH #4)
  const isConsole = t.kind === "console";
  const isSamagra = t.kind === "samagra";

  const [menu, setMenu] = useState<MenuState | null>(null);
  const [startOpen, setStartOpen] = useState(false);
  const [now, setNow] = useState(() => new Date());

  // Live clock — 1s tick, cleared on unmount.
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Context-menu openers — one per right-click surface (README §Context menus).
  const openWindowMenu = useCallback((id: string, x: number, y: number) => {
    setMenu({ kind: "window", winId: id, x, y });
  }, []);
  const openAppMenu = useCallback((appId: AppId, x: number, y: number) => {
    setMenu({ kind: "app", appId, x, y });
  }, []);
  const openDesktopMenu = useCallback((x: number, y: number) => {
    setStartOpen(false);
    setMenu({ kind: "desktop", x, y });
  }, []);

  // Close every open window / every window of one app (desktop + dock-icon menus).
  // Snapshot the ids first so closing (which mutates `windows`) can't skip any.
  const closeAll = useCallback(() => {
    wmStore
      .getState()
      .windows.map((w) => w.id)
      .forEach((id) => closeApp(id));
  }, [closeApp]);
  const closeWindowsOf = useCallback(
    (appId: AppId) => {
      wmStore
        .getState()
        .windows.filter((w) => w.app === appId)
        .map((w) => w.id)
        .forEach((id) => closeApp(id));
    },
    [closeApp],
  );

  // Active = the top-most (highest z) non-minimized window.
  const active = useMemo<WindowState | null>(() => {
    const live = windows.filter((w) => !w.min);
    if (live.length === 0) return null;
    return live.reduce((a, b) => (b.z > a.z ? b : a));
  }, [windows]);

  // App ids with at least one open window — drives the samagra Rail's running
  // tint + left accent bar (renderDock samagra `running(id)`, .dc.html L1018).
  const runningApps = useMemo<AppId[]>(
    () => Array.from(new Set(windows.map((w) => w.app))),
    [windows],
  );

  // Taskbar click on a running window (renderTaskbar L1042): restore it if minimized
  // (openApp un-minimizes + bumps z for an already-open app — store §1.4 step 2),
  // else just focus it.
  const selectWindow = useCallback(
    (id: string) => {
      const w = wmStore.getState().windows.find((x) => x.id === id);
      if (!w) return;
      if (w.min) openApp(w.app);
      else focus(id);
    },
    [focus, openApp],
  );

  const handleOpen = useCallback(
    (id: AppId) => {
      openApp(id);
      setStartOpen(false);
    },
    [openApp],
  );

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    if (!menu) return [];
    const close = () => setMenu(null);

    // Window / taskbar-button menu (README §Context menus — window\title bar).
    if (menu.kind === "window") {
      const win = windows.find((w) => w.id === menu.winId);
      if (!win) return [];
      return [
        { label: "Bring to front", onSelect: () => { focus(win.id); close(); } },
        { label: win.max ? "Restore" : "Maximize", onSelect: () => { toggleMax(win.id); close(); } },
        { label: "Minimize", onSelect: () => { minimize(win.id); close(); } },
        { divider: true },
        { label: "Close", danger: true, onSelect: () => { closeApp(win.id); close(); } },
      ];
    }

    // Dock / rail icon menu (README §Context menus — dock icon).
    if (menu.kind === "app") {
      const appId = menu.appId;
      const hasWindow = windows.some((w) => w.app === appId);
      return [
        { label: "Open", icon: appId, onSelect: () => { openApp(appId); close(); } },
        {
          label: "Close window",
          danger: true,
          disabled: !hasWindow,
          onSelect: () => { closeWindowsOf(appId); close(); },
        },
      ];
    }

    // Desktop menu (README §Context menus — desktop).
    return [
      { label: "New Terminal", icon: "terminal", onSelect: () => { openApp("terminal"); close(); } },
      { label: "Open Dashboard", icon: "dashboard", onSelect: () => { openApp("dashboard"); close(); } },
      { divider: true },
      { header: "Appearance" },
      ...THEME_OPTIONS.map((o) => ({
        label: o.label,
        checked: theme === o.id,
        onSelect: () => { setTheme(o.id); close(); },
      })),
      { divider: true },
      { label: "Tile windows", disabled: windows.length === 0, onSelect: () => { tile(); close(); } },
      {
        label: device === "mobile" ? "Switch to PC" : "Switch to Mobile",
        onSelect: () => { setDevice(device === "mobile" ? "pc" : "mobile"); close(); },
      },
      {
        label: "Close all windows",
        danger: true,
        disabled: windows.length === 0,
        onSelect: () => { closeAll(); close(); },
      },
    ];
  }, [
    menu,
    windows,
    focus,
    toggleMax,
    minimize,
    closeApp,
    openApp,
    closeWindowsOf,
    theme,
    setTheme,
    device,
    setDevice,
    tile,
    closeAll,
  ]);

  // E3 — mobile device mode: the desktop windowing shell is replaced by the phone
  // frame (proto §7). Declared AFTER every hook above so the hook order is stable.
  // The shell root keeps the --samagra-* CSS vars so app bodies resolve var()s; the
  // desktop context menu is intentionally NOT wired here (no right-click desktop on
  // a phone). Tapping a launcher opens the app full-screen; Home returns to the grid.
  if (device === "mobile") {
    const MobileBody = mobileApp ? appComponent(mobileApp) : null;
    return (
      <div
        id="samagra-os-shell"
        style={{
          ...(cssVars(t) as CSSProperties),
          position: "fixed",
          inset: 0,
          overflow: "hidden",
          background: t.bg,
          font: `13px ${t.font}`,
          color: t.text,
        }}
      >
        <Mobile
          theme={theme}
          clock={fmtClock(now)}
          mobileApp={mobileApp}
          onOpen={openMobileApp}
          onHome={goHome}
          appBody={
            MobileBody ? (
              <Suspense fallback={null}>
                <MobileBody />
              </Suspense>
            ) : null
          }
        />
      </div>
    );
  }

  return (
    <div
      id="samagra-os-shell"
      onClick={() => {
        setMenu(null);
        setStartOpen(false);
      }}
      onContextMenu={(e) => {
        // Only a right-click on the BARE desktop background opens the desktop menu;
        // right-clicks that originate on a window / dock / rail / taskbar handle their
        // own context menu (or none) and must not be overridden here.
        if (e.target !== e.currentTarget) return;
        e.preventDefault();
        openDesktopMenu(e.clientX, e.clientY);
      }}
      style={{
        // Expose the active theme's tokens as --samagra-* CSS vars so every
        // var(--samagra-*) reference (chrome + app bodies, incl. the Clock face
        // SVG fill/stroke) resolves; without this they fall back (black clock).
        ...(cssVars(t) as CSSProperties),
        position: "fixed",
        inset: 0,
        overflow: "hidden",
        background: t.bg,
        font: `13px ${t.font}`,
        color: t.text,
      }}
    >
      {/* Top bar — aqua/samagra only (TopBar renders null for console). */}
      <TopBar
        theme={theme}
        activeTitle={active ? APPS[active.app].name : ""}
        clock={fmtClock(now)}
        onOpenClock={() => openApp("clock")}
      />

      {windows.map((win) => {
        const Body = appComponent(win.app);
        return (
          <WindowFrame
            key={win.id}
            win={win}
            theme={theme}
            title={APPS[win.app].name}
            active={active?.id === win.id}
            onFocus={focus}
            onClose={closeApp}
            onMinimize={minimize}
            onToggleMax={toggleMax}
            onContextMenu={openWindowMenu}
            onMove={move}
            onResize={resize}
          >
            <Suspense fallback={null}>
              <Body />
            </Suspense>
          </WindowFrame>
        );
      })}

      {/* Theme-driven dock chrome (FD1): console → bottom Taskbar + Start menu;
          samagra → left Rail; aqua → bottom-center floating Dock. Each launcher
          surface also dispatches a right-click → the dock-icon menu. */}
      {isConsole ? (
        <Taskbar
          theme={theme}
          windows={windows}
          activeId={active?.id ?? null}
          clock={fmtClock(now)}
          startOpen={startOpen}
          onToggleStart={() => setStartOpen((v) => !v)}
          onSelectWindow={selectWindow}
          onWindowContextMenu={openWindowMenu}
          onOpenClock={() => openApp("clock")}
        >
          {startOpen && <StartMenu theme={theme} onOpen={handleOpen} />}
        </Taskbar>
      ) : isSamagra ? (
        <Rail theme={theme} onOpen={openApp} running={runningApps} onAppContextMenu={openAppMenu} />
      ) : (
        <Dock theme={theme} onOpen={openApp} onAppContextMenu={openAppMenu} />
      )}

      {menu && <ContextMenu x={menu.x} y={menu.y} items={menuItems} theme={theme} />}
    </div>
  );
}

export { wmStore, themeStore };
