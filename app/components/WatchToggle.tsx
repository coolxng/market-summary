"use client";

import { useEffect, useState } from "react";
import { readWatchlist, subscribeWatchlist, WATCHLIST_MAX, writeWatchlist } from "../lib/watchlist";

/** `compact` draws an icon-only round button (+ / ✓) for tight spots such as the phone chart header. */
export default function WatchToggle({ slug, name, compact = false }: { slug: string; name: string; compact?: boolean }) {
  const [list, setList] = useState<string[] | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setList(readWatchlist()));
    const unsubscribe = subscribeWatchlist(setList);
    return () => {
      window.cancelAnimationFrame(frame);
      unsubscribe();
    };
  }, []);

  const watched = list?.includes(slug) ?? false;
  const full = !watched && (list?.length ?? 0) >= WATCHLIST_MAX;

  const toggle = () => {
    const current = readWatchlist();
    setList(writeWatchlist(current.includes(slug) ? current.filter((item) => item !== slug) : [...current, slug]));
  };

  if (compact) {
    const label = watched ? `Remove ${name} from watchlist` : full ? `Watchlist is full (${WATCHLIST_MAX})` : `Add ${name} to watchlist`;
    return (
      <button type="button" className="watch-toggle watch-toggle--compact" onClick={toggle} disabled={list === null || full} aria-pressed={watched} aria-label={label} title={label}>
        <svg viewBox="0 0 24 24" aria-hidden="true">{watched ? <path d="m6 12.5 4 4 8-9" /> : <path d="M12 6v12M6 12h12" />}</svg>
      </button>
    );
  }

  return (
    <>
      <button type="button" className="watch-toggle" onClick={toggle} disabled={list === null || full} aria-pressed={watched}>
        {watched ? "✓ On your watchlist" : "+ Add to watchlist"}
        <span className="visually-hidden"> {name}</span>
      </button>
      {full && <small className="watch-toggle__note">Watchlist is full ({WATCHLIST_MAX}). Remove a symbol first.</small>}
    </>
  );
}
