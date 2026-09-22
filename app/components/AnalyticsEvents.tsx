"use client";

import { useEffect } from "react";
import { track } from "../lib/analytics";
import { WATCHLIST_EVENT } from "../lib/watchlist";

/** Page-type and interaction events. Renders nothing; no-op without a provider. */
export default function AnalyticsEvents() {
  useEffect(() => {
    const path = window.location.pathname.replace(process.env.NEXT_PUBLIC_BASE_PATH ?? "", "");
    const session = path.match(/^\/reports\/(\d{4}-\d{2}-\d{2})\/?$/);
    const asset = path.match(/^\/assets\/([\w-]+)\/?$/);
    if (session) track("Archived session opened", { session: session[1] });
    else if (/^\/reports\/?$/.test(path)) track("Archive opened");
    else if (asset) track("Asset page opened", { asset: asset[1] });
    else if (/^\/morning\/?$/.test(path)) track("Morning Tape opened");

    const onClick = (event: MouseEvent) => {
      const link = (event.target as HTMLElement | null)?.closest<HTMLAnchorElement>("a[data-outbound]");
      if (!link) return;
      const kind = link.dataset.outbound ?? "source";
      const host = (() => { try { return new URL(link.href).hostname; } catch { return "unknown"; } })();
      track(kind === "calendar" ? "Calendar source click" : "Outbound source click", { kind, host });
    };
    const onWatchlist = (event: Event) => track("Watchlist updated", { size: ((event as CustomEvent<string[]>).detail ?? []).length });
    document.addEventListener("click", onClick);
    window.addEventListener(WATCHLIST_EVENT, onWatchlist);
    return () => {
      document.removeEventListener("click", onClick);
      window.removeEventListener(WATCHLIST_EVENT, onWatchlist);
    };
  }, []);

  return null;
}
