"use client";

import { useEffect, useState } from "react";
import { nextTradingDayAt } from "../lib/publication";

const MORNING_HOUR = 7;
const MORNING_MINUTE = 45;

function remaining(now: Date, target: Date) {
  const minutes = Math.max(0, Math.ceil((target.getTime() - now.getTime()) / 60000));
  const hours = Math.floor(minutes / 60);
  if (hours >= 48) return `${Math.floor(hours / 24)}D ${hours % 24}H`;
  return hours ? `${hours}H ${String(minutes % 60).padStart(2, "0")}M` : `${minutes}M`;
}

/** Live countdown to the next scheduled Pre-Market brief (7:45 AM Central, NYSE trading days). */
export default function MorningCountdown() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setNow(new Date()));
    const interval = window.setInterval(() => setNow(new Date()), 30000);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearInterval(interval);
    };
  }, []);

  const target = now ? nextTradingDayAt(now, MORNING_HOUR, MORNING_MINUTE) : null;
  const when = target
    ? new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", weekday: "long", hour: "numeric", minute: "2-digit" }).format(target)
    : "7:45 AM CT on the next trading day";

  return (
    <div className="morning-countdown" role="status">
      <span>NEXT PRE-MARKET BRIEF IN</span>
      <strong>{now && target ? remaining(now, target) : "—"}</strong>
      <small>{target ? `${when} CT` : when}</small>
    </div>
  );
}
