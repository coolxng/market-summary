"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { flushSync } from "react-dom";
import AssetLogo from "./AssetLogo";
import type { AssetSummary } from "../lib/assetSummary";

export type SearchIndexAsset = Pick<AssetSummary, "slug" | "symbol" | "name" | "category" | "logo" | "priceText" | "changeText" | "tone">;
export type SearchIndexReport = { date: string; displayDate: string; headline: string };
export type SearchIndex = { assets: SearchIndexAsset[]; reports: SearchIndexReport[] };

const MAX_ASSETS = 6;
const MAX_REPORTS = 3;

// One download per page view, shared by every header instance; a failed load
// is forgotten so the next focus retries.
let indexRequest: Promise<SearchIndex> | null = null;
function loadIndex(url: string) {
  indexRequest ??= fetch(url)
    .then((response) => {
      if (!response.ok) throw new Error(`search index ${response.status}`);
      return response.json() as Promise<SearchIndex>;
    })
    .catch((error) => {
      indexRequest = null;
      throw error;
    });
  return indexRequest;
}

const wordStarts = (text: string, query: string) => text.split(/[\s\-&./()]+/).some((word) => word.startsWith(query));

/** Lower is better; null means no match. Symbol hits outrank name hits so "hood" finds HOOD first. */
function assetScore(asset: SearchIndexAsset, query: string) {
  const symbol = asset.symbol.toLowerCase().replace(/^\^/, "");
  const name = asset.name.toLowerCase();
  if (symbol === query || name === query) return 0;
  if (symbol.startsWith(query)) return 1;
  if (name.startsWith(query)) return 2;
  if (wordStarts(name, query)) return 3;
  // Mid-word hits are noise for one or two letters ("nv" inside "Invesco").
  if (query.length > 2 && (name.includes(query) || symbol.includes(query))) return 4;
  if (asset.category.toLowerCase().startsWith(query)) return 5;
  return null;
}

function reportScore(report: SearchIndexReport, query: string) {
  if (report.date.startsWith(query) || report.displayDate.toLowerCase().startsWith(query)) return 0;
  const headline = report.headline.toLowerCase();
  if (wordStarts(headline, query)) return 1;
  if (query.length > 2 && (headline.includes(query) || report.displayDate.toLowerCase().includes(query))) return 2;
  return null;
}

function rank<T>(items: T[], score: (item: T) => number | null, limit: number) {
  return items
    .map((item, order) => ({ item, order, score: score(item) }))
    .filter((entry): entry is { item: T; order: number; score: number } => entry.score !== null)
    .sort((a, b) => a.score - b.score || a.order - b.order)
    .slice(0, limit)
    .map((entry) => entry.item);
}

/** Wraps the first case-insensitive occurrence of the query in <mark>. */
function highlight(text: string, query: string): ReactNode {
  const at = query ? text.toLowerCase().indexOf(query) : -1;
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>;
}

type Option =
  | { kind: "asset"; href: string; asset: SearchIndexAsset }
  | { kind: "report"; href: string; report: SearchIndexReport }
  | { kind: "all"; href: string };

/**
 * Masthead search with type-ahead suggestions. Without JavaScript it is a
 * plain GET form to the search page; once hydrated it lazily loads a small
 * index on first focus and suggests assets and sessions as you type.
 */
export default function HeaderSearch({ root, slashShortcut }: { root: string; slashShortcut: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [index, setIndex] = useState<SearchIndex | null>(null);
  const [failed, setFailed] = useState(false);
  // Narrow screens show only a search icon; this is true while it is expanded into the full bar.
  const [revealed, setRevealed] = useState(false);

  const searchHref = `${root}search/`;
  const normalized = query.trim().toLowerCase();

  const { groups, options } = useMemo(() => {
    if (!index) return { groups: [], options: [] as Option[] };
    const assets = normalized ? rank(index.assets, (asset) => assetScore(asset, normalized), MAX_ASSETS) : index.assets.slice(0, 5);
    const reports = normalized ? rank(index.reports, (report) => reportScore(report, normalized), MAX_REPORTS) : index.reports.slice(0, MAX_REPORTS);
    const assetOptions: Option[] = assets.map((asset) => ({ kind: "asset", href: `${root}assets/${asset.slug}/`, asset }));
    const reportOptions: Option[] = reports.map((report) => ({ kind: "report", href: `${root}reports/${report.date}/`, report }));
    const all: Option[] = normalized && (assets.length || reports.length)
      ? [{ kind: "all", href: `${searchHref}?q=${encodeURIComponent(query.trim())}` }]
      : [];
    return {
      groups: [
        { label: normalized ? "Assets" : "Popular", options: assetOptions },
        { label: normalized ? "Sessions" : "Latest sessions", options: reportOptions },
      ].filter((group) => group.options.length > 0),
      options: [...assetOptions, ...reportOptions, ...all],
    };
  }, [index, normalized, query, root, searchHref]);

  const showAll = options.at(-1)?.kind === "all";

  const ensureIndex = () => {
    if (index) return;
    setFailed(false);
    loadIndex(`${root}search-index.json`).then(setIndex, () => setFailed(true));
  };

  const close = () => {
    setOpen(false);
    setActive(-1);
    setRevealed(false);
  };

  // Rendered synchronously so the input exists to take focus inside the same
  // tap, which is what lets mobile browsers raise the keyboard.
  const reveal = () => {
    flushSync(() => setRevealed(true));
    inputRef.current?.focus({ preventScroll: true });
  };

  // "/" (where the page doesn't already own it) and Ctrl/Cmd+K jump to the bar.
  // Capture phase so this runs before the page's KeyboardShortcuts handler,
  // which skips events that were already handled.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const input = inputRef.current;
      const compact = (toggleRef.current?.getClientRects().length ?? 0) > 0;
      if (!input || (!compact && input.getClientRects().length === 0)) return;
      const commandK = (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "k";
      const slash = slashShortcut && event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey;
      if (!commandK && !slash) return;
      if (slash && (event.target as HTMLElement | null)?.closest("input, textarea, select, [contenteditable='true'], [role='group'], dialog")) return;
      event.preventDefault();
      if (compact) flushSync(() => setRevealed(true));
      input.focus({ preventScroll: true });
      input.select();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [slashShortcut]);

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (!options.length) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current < 0 && step < 0 ? options.length - 1 : (current + step + options.length) % options.length));
    } else if (event.key === "Enter") {
      const option = open ? options[active] : undefined;
      if (option) {
        event.preventDefault();
        window.location.href = option.href;
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      if (query) {
        setQuery("");
        setActive(-1);
      } else {
        close();
        inputRef.current?.blur();
      }
    } else if (event.key === "Tab") {
      close();
    }
  };

  const optionId = (position: number) => `${listId}-${position}`;
  const row = (option: Option, children: ReactNode) => {
    const current = options.indexOf(option);
    return (
      <a
        key={option.href}
        id={optionId(current)}
        href={option.href}
        role="option"
        aria-selected={current === active}
        tabIndex={-1}
        className={`site-search__option${option.kind === "all" ? " site-search__option--all" : ""}`}
        onMouseDown={(event) => event.preventDefault()}
        onMouseMove={() => { if (active !== current) setActive(current); }}
      >
        {children}
      </a>
    );
  };

  let status: string | null = null;
  if (failed) status = "Suggestions unavailable. Press Enter to search.";
  else if (!index) status = "Loading…";
  else if (normalized && options.length === 0) status = `No matches for “${query.trim()}”`;

  const expanded = open && (status !== null || options.length > 0);

  return (
    <form
      className="site-search"
      action={searchHref}
      method="get"
      role="search"
      data-revealed={revealed ? "" : undefined}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close(); }}
    >
      <button ref={toggleRef} type="button" className="site-search__toggle" aria-label="Search reports and assets" onClick={reveal}>
        <svg className="site-search__icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4 4" />
        </svg>
      </button>
      <label className="site-search__field">
        <svg className="site-search__icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4 4" />
        </svg>
        <input
          ref={inputRef}
          type="search"
          name="q"
          value={query}
          placeholder="Search reports, assets..."
          aria-label="Search reports and assets"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-activedescendant={expanded && active >= 0 ? optionId(active) : undefined}
          autoComplete="off"
          spellCheck={false}
          enterKeyHint="search"
          onFocus={() => { setOpen(true); ensureIndex(); }}
          onPointerEnter={ensureIndex}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            // Keep the combobox input as the active focus target while typing.
            // Automatically assigning aria-activedescendant here can make browsers
            // scroll the document toward the sticky suggestion list on each keypress.
            setActive(-1);
          }}
          onKeyDown={onKeyDown}
        />
        {(query || revealed) && (
          <button
            type="button"
            className="site-search__clear"
            aria-label={query ? "Clear search" : "Close search"}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              if (query) {
                setQuery("");
                setActive(-1);
                inputRef.current?.focus({ preventScroll: true });
              } else {
                close();
                inputRef.current?.blur();
                toggleRef.current?.focus();
              }
            }}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 8 8 8M16 8l-8 8" /></svg>
          </button>
        )}
      </label>

      <div className="site-search__panel" id={listId} role="listbox" aria-label="Search suggestions" data-open={expanded ? "" : undefined} aria-hidden={!expanded}>
        {status && <p className="site-search__status" role="status">{status}</p>}
        {groups.map((group) => (
          <div className="site-search__group" role="presentation" key={group.label}>
            <p className="site-search__label" role="presentation">{group.label}</p>
            {group.options.map((option) =>
              option.kind === "asset"
                ? row(option, (
                  <>
                    <AssetLogo src={option.asset.logo} symbol={option.asset.symbol} size={26} />
                    <span className="site-search__text">
                      <strong>{highlight(option.asset.name, normalized)}</strong>
                      <small>{highlight(option.asset.symbol, normalized)} · {option.asset.category}</small>
                    </span>
                    <span className="site-search__quote">
                      <b>{option.asset.priceText}</b>
                      <small className={option.asset.tone}>{option.asset.changeText}</small>
                    </span>
                  </>
                ))
                : option.kind === "report"
                  ? row(option, (
                    <>
                      <span className="site-search__mark" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M7 3.5h7l4 4V20.5H7z M14 3.5v4h4 M10 12h5M10 15.5h5" /></svg>
                      </span>
                      <span className="site-search__text">
                        <strong>{highlight(option.report.headline, normalized)}</strong>
                        <small>{highlight(option.report.displayDate, normalized)}</small>
                      </span>
                    </>
                  ))
                  : null,
            )}
          </div>
        ))}
        {showAll && row(options.at(-1)!, <>See all results for “{query.trim()}”<span aria-hidden="true">→</span></>)}
      </div>
    </form>
  );
}
