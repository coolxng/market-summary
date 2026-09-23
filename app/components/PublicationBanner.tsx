"use client";

import { useEffect, useState } from "react";
import { getPublicationIndicator, type PublicationIndicator } from "../lib/publication";

const SCHEDULED: PublicationIndicator = {
  mode: "countdown",
  label: "NEXT ISSUE IN",
  value: "SCHEDULED",
  meta: "30 min after U.S. market close",
};

export default function PublicationBanner({ sessionDate, generatedAt, compact = false, className = "" }: { sessionDate: string; generatedAt: string; compact?: boolean; className?: string }) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const update = () => setNow(new Date());
    const frame = window.requestAnimationFrame(update);
    const interval = window.setInterval(update, 60000);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearInterval(interval);
    };
  }, []);

  const status = now ? getPublicationIndicator(now, sessionDate, new Date(generatedAt)) : SCHEDULED;

  // One-line form for the report bar and the opening metadata line.
  if (compact) {
    return (
      <span className={`publication-compact publication-compact--${status.mode} ${className}`.trim()} role="status" title={status.meta}>
        <i className="publication-banner__dot" aria-hidden="true" />
        <span className="publication-compact__label">{status.label}</span>
        <strong>{status.value}</strong>
        <span className="visually-hidden">. {status.meta}</span>
      </span>
    );
  }

  return (
    <div className={`publication-banner publication-banner--${status.mode}`} role="status">
      <span className="publication-banner__status">
        <i className="publication-banner__dot" aria-hidden="true" />
        <span className="publication-banner__label">{status.label}</span>
        <strong className="publication-banner__value">{status.value}</strong>
      </span>
      <span className="publication-banner__divider" aria-hidden="true" />
      <span className="publication-banner__meta">{status.meta}</span>
    </div>
  );
}
