"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export type ReportChapter = { id: string; label: string; number?: string };

/**
 * Sticky in-report navigation. It only ever scrolls within the current report;
 * site-level destinations stay in the masthead. The active chapter is derived
 * from scroll position on the client, so the static markup works without it.
 */
export default function ReportNav({
  chapters,
  edition,
  archived,
  latestHref,
  status,
}: {
  chapters: ReportChapter[];
  edition: string;
  archived: boolean;
  latestHref?: string;
  /** Publication status for the latest edition, shown at the bar's end on wide screens. */
  status?: ReactNode;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const bar = useRef<HTMLElement>(null);
  const list = useRef<HTMLOListElement>(null);
  // A chapter chosen from the bar stays current while the page travels to it,
  // instead of the highlight trailing through every chapter it scrolls past.
  const held = useRef<string | null>(null);
  const release = useRef<() => void>(() => {});

  useEffect(() => {
    let frame = 0;
    let settle = 0;
    const update = () => {
      frame = 0;
      setScrolled(window.scrollY > window.innerHeight * 0.9);
      if (held.current) { setActive(held.current); return; }
      const navBottom = bar.current?.getBoundingClientRect().bottom ?? 0;
      // A chapter becomes current once its top passes a line a quarter of the
      // way down the visible area below the sticky bars.
      const line = navBottom + (window.innerHeight - navBottom) * 0.25;
      let current: string | null = null;
      let currentElement: HTMLElement | null = null;
      for (const chapter of chapters) {
        const element = document.getElementById(chapter.id);
        if (element && element.getBoundingClientRect().top <= line) {
          current = chapter.id;
          currentElement = element;
        }
      }
      // Below the final chapter (reference, methodology, footer) no chapter is
      // current; the end matter is intentionally not part of the chapter list.
      if (current === chapters.at(-1)?.id && currentElement && currentElement.getBoundingClientRect().bottom <= line) current = null;
      setActive(current);
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update); };
    const unhold = () => {
      window.clearTimeout(settle);
      if (!held.current) return;
      held.current = null;
      schedule();
    };
    // Let go once the page has been still for a moment (the chapter jump is
    // animated frame by frame, so scrollend would fire too early), or as soon as
    // the reader takes over scrolling.
    const waitForRest = () => {
      window.clearTimeout(settle);
      if (held.current) settle = window.setTimeout(unhold, 180);
    };
    const onScroll = () => { waitForRest(); schedule(); };
    release.current = waitForRest;
    schedule();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", schedule);
    for (const type of ["wheel", "touchstart", "keydown"]) window.addEventListener(type, unhold, { passive: true });
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.clearTimeout(settle);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("hashchange", schedule);
      for (const type of ["wheel", "touchstart", "keydown"]) window.removeEventListener(type, unhold);
    };
  }, [chapters]);

  // Fade whichever edge of the chapter row still has hidden links (mobile).
  useEffect(() => {
    const container = list.current;
    if (!container) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const max = container.scrollWidth - container.clientWidth;
      container.toggleAttribute("data-more-start", container.scrollLeft > 2);
      container.toggleAttribute("data-more-end", max - container.scrollLeft > 2);
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update); };
    update();
    container.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      container.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [chapters]);

  // Keep the active link visible when the chapter row scrolls sideways (mobile),
  // centring it so the neighbouring chapters stay in view on both sides.
  useEffect(() => {
    const container = list.current;
    const link = container?.querySelector<HTMLElement>('[aria-current="location"]');
    if (!container || !link || container.scrollWidth <= container.clientWidth) return;
    const box = container.getBoundingClientRect();
    const rect = link.getBoundingClientRect();
    if (rect.left >= box.left + 24 && rect.right <= box.right - 32) return;
    const target = container.scrollLeft + rect.left - box.left - (box.width - rect.width) / 2;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    container.scrollTo({ left: Math.max(0, target), behavior: reduce ? "auto" : "smooth" });
  }, [active]);

  return (
    <nav className={`report-nav${archived ? " report-nav--archived" : ""}`} aria-label="Report chapters" ref={bar}>
      <div className="report-nav__inner">
        <a className="report-nav__edition" href="#top" title="Back to the top of this report">
          <span>{archived ? "Archived" : "Latest"}</span>
          <b>{edition}</b>
        </a>
        <ol ref={list}>
          {chapters.map((chapter) => (
            <li key={chapter.id}>
              <a
                href={`#${chapter.id}`}
                onClick={() => { held.current = chapter.id; setActive(chapter.id); release.current(); }}
                aria-current={active === chapter.id ? "location" : undefined}>
                {chapter.number && <small aria-hidden="true">{chapter.number}</small>}
                {chapter.label}
              </a>
            </li>
          ))}
        </ol>
        <div className="report-nav__end">
          {archived && latestHref && <a className="report-nav__latest" href={latestHref}>Latest edition →</a>}
          {status && <span className="report-nav__status">{status}</span>}
          <a className={`report-nav__top${scrolled ? " is-visible" : ""}`} href="#top" aria-hidden={scrolled ? undefined : true} tabIndex={scrolled ? undefined : -1}>
            Top <span aria-hidden="true">↑</span>
          </a>
        </div>
      </div>
    </nav>
  );
}
