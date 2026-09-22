"use client";

import { THEME_STORAGE_KEY, THEME_COLORS, type Theme } from "../lib/theme";

// The visible label is chosen by CSS from <html data-theme>, which the inline
// head script sets before first paint, so there is no label or colour flash and
// no hydration mismatch. This component only handles the click.
export default function ThemeToggle() {
  const toggle = () => {
    const root = document.documentElement;
    const next: Theme = root.dataset.theme === "ink" ? "paper" : "ink";
    root.dataset.theme = next;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[next]);
    const favicon = document.getElementById("site-favicon") as HTMLLinkElement | null;
    if (favicon) favicon.href = new URL(next === "ink" ? "favicon-dark.svg" : "favicon-light.svg", favicon.href).href;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Private browsing can block storage; the toggle still works for this page view.
    }
  };

  return (
    <button className="theme-toggle" type="button" onClick={toggle} aria-label="Toggle light and dark theme">
      <span className="theme-toggle__icon" aria-hidden="true">
        <span className="theme-only-paper">◐</span>
        <span className="theme-only-ink">◑</span>
      </span>
      <span className="theme-toggle__label">
        <span className="theme-only-paper">Ink</span>
        <span className="theme-only-ink">Paper</span>
      </span>
    </button>
  );
}
