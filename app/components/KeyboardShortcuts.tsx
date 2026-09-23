"use client";

import { useEffect, useRef } from "react";

export type ShortcutTarget =
  | { kind: "href"; href: string }
  | { kind: "anchor"; id: string }
  | { kind: "focus"; id: string };

export type Shortcut = ShortcutTarget & { label: string };

const KEY_LABEL: Record<string, string> = { ArrowLeft: "←", ArrowRight: "→", "/": "/" };

/**
 * Single-key shortcuts plus a "?" help dialog. Keys never fire while typing,
 * with Ctrl/Cmd/Alt held, or while a chart, dialog or form control has focus,
 * so browser and assistive-technology shortcuts keep working.
 */
export default function KeyboardShortcuts({ bindings }: { bindings: Record<string, Shortcut> }) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true'], [role='group'], dialog")) return;
      if (event.key === "?") {
        event.preventDefault();
        dialog.current?.showModal();
        return;
      }

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
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      if (!element.hasAttribute("tabindex")) element.setAttribute("tabindex", "-1");
      element.focus({ preventScroll: true });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bindings]);

  return (
    <>
      <button type="button" className="shortcut-button" onClick={() => dialog.current?.showModal()} aria-haspopup="dialog">
        Keyboard shortcuts <kbd>?</kbd>
      </button>
      <dialog ref={dialog} className="shortcut-dialog" aria-labelledby="shortcut-title" onClick={(event) => { if (event.target === dialog.current) dialog.current?.close(); }}>
        <div>
          <p className="section-kicker" id="shortcut-title">KEYBOARD SHORTCUTS</p>
          <dl>
            {Object.entries(bindings).map(([key, binding]) => (
              <div key={key}><dt><kbd>{KEY_LABEL[key] ?? key.toUpperCase()}</kbd></dt><dd>{binding.label}</dd></div>
            ))}
            <div><dt><kbd>?</kbd></dt><dd>Show this list</dd></div>
          </dl>
          <p>Shortcuts pause while you type in a field or while a chart is focused. Charts use ← → to step through points.</p>
          <form method="dialog"><button type="submit">Close</button></form>
        </div>
      </dialog>
    </>
  );
}
