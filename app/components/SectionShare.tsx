"use client";

import { useState } from "react";

/**
 * Shares a permanent link to one section of a specific session. The URL is
 * the archived issue (never the rolling homepage), so a shared link keeps
 * showing the numbers it was shared with.
 */
export default function SectionShare({ url, title, label = "Share" }: { url: string; title: string; label?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  const share = async () => {
    try {
      if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
        await navigator.share({ title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setState("copied");
    } catch (error) {
      if ((error as DOMException)?.name === "AbortError") return;
      setState("failed");
    }
    window.setTimeout(() => setState("idle"), 2200);
  };

  return (
    <span className="section-share">
      <button type="button" onClick={share} aria-label={`${label}: copy a permanent link to ${title}`}>
        {state === "copied" ? "Link copied ✓" : `${label} ↗`}
      </button>
      {state === "failed" && <input readOnly value={url} aria-label="Permanent link" onFocus={(event) => event.currentTarget.select()} />}
      <span className="visually-hidden" aria-live="polite">{state === "copied" ? "Link copied to clipboard" : ""}</span>
    </span>
  );
}
