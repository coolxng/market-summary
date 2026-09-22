import { assetBySlug } from "./assets";

// Local-only watchlist. Stored per browser, never sent anywhere, and separate
// from the theme preference. Only slugs from the tracked asset catalog are kept.

export const WATCHLIST_STORAGE_KEY = "daily-tape-watchlist";
export const WATCHLIST_MAX = 20;
export const WATCHLIST_EVENT = "daily-tape-watchlist-change";

export function sanitizeWatchlist(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  for (const item of value) {
    if (typeof item === "string" && assetBySlug[item] && !seen.has(item)) seen.add(item);
    if (seen.size >= WATCHLIST_MAX) break;
  }
  return [...seen];
}

export function readWatchlist(): string[] {
  try {
    return sanitizeWatchlist(JSON.parse(window.localStorage.getItem(WATCHLIST_STORAGE_KEY) || "[]"));
  } catch {
    return [];
  }
}

export function writeWatchlist(slugs: string[]) {
  const clean = sanitizeWatchlist(slugs);
  try {
    window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(clean));
  } catch {
    // Storage can be unavailable (private mode); the in-memory list still updates.
  }
  window.dispatchEvent(new CustomEvent(WATCHLIST_EVENT, { detail: clean }));
  return clean;
}

/** Subscribe to changes from this tab (custom event) and other tabs (storage event). */
export function subscribeWatchlist(callback: (slugs: string[]) => void) {
  const onCustom = (event: Event) => callback((event as CustomEvent<string[]>).detail ?? readWatchlist());
  const onStorage = (event: StorageEvent) => {
    if (event.key === WATCHLIST_STORAGE_KEY) callback(readWatchlist());
  };
  window.addEventListener(WATCHLIST_EVENT, onCustom);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(WATCHLIST_EVENT, onCustom);
    window.removeEventListener("storage", onStorage);
  };
}
