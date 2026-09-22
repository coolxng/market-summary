"use client";

import { useEffect, useState } from "react";
import { centralCalendarDate, calendarKey } from "../lib/publication";

/**
 * Warns readers when the edition on screen is not today's (Central Time).
 * The page is static, so the check has to run against the viewer's clock.
 */
export default function EditionFreshness({ editionDate, label }: { editionDate: string | null; label: string }) {
  const [today, setToday] = useState<string | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setToday(calendarKey(centralCalendarDate(new Date()))));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  if (!today || !editionDate || editionDate === today) return null;
  const shown = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" })
    .format(new Date(`${editionDate}T12:00:00Z`));
  return (
    <p className="edition-warning" role="status">
      <strong>Not today&apos;s edition.</strong> This {label} is from {shown}. Prices and events below reflect that morning, not the current session.
    </p>
  );
}
