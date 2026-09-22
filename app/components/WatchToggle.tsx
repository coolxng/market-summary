"use client";

import { useEffect, useState } from "react";
import { readWatchlist, subscribeWatchlist, WATCHLIST_MAX, writeWatchlist } from "../lib/watchlist";

export default function WatchToggle({ slug, name }: { slug: string; name: string }) {
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
