"use client";

import { useEffect } from "react";

export type ShortcutTarget =
  | { kind: "href"; href: string }
  | { kind: "anchor"; id: string }
  | { kind: "focus"; id: string };

// Single-key shortcuts that never fire while typing, with modifier keys held,
// or when an interactive widget (chart, select, button) has focus.
export default function KeyboardShortcuts({ bindings }: { bindings: Record<string, ShortcutTarget> }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true'], [role='group'], [role='dialog']")) return;

      const binding = bindings[event.key.length === 1 ? event.key.toLowerCase() : event.key];
      if (!binding) return;
      event.preventDefault();
      if (binding.kind === "href") {
        window.location.href = binding.href;
        return;
      }
      const element = document.getElementById(binding.id);
      if (!element) return;
      if (binding.kind === "focus") {
        element.focus();
        return;
      }
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      element.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      if (!element.hasAttribute("tabindex")) element.setAttribute("tabindex", "-1");
      element.focus({ preventScroll: true });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bindings]);

  return null;
}
