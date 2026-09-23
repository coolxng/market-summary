"use client";

import { useEffect, useRef, useState } from "react";

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
}: {
  chapters: ReportChapter[];
  edition: string;
  archived: boolean;
  latestHref?: string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const bar = useRef<HTMLElement>(null);
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
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
      setScrolled(window.scrollY > window.innerHeight * 0.9);
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update); };
    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", schedule);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("hashchange", schedule);
    };
  }, [chapters]);

  // Keep the active link visible when the chapter row scrolls sideways (mobile).
  useEffect(() => {
    const container = list.current;
    const link = container?.querySelector<HTMLElement>('[aria-current="location"]');
    if (!container || !link || container.scrollWidth <= container.clientWidth) return;
    const left = link.offsetLeft - container.offsetLeft;
    if (left < container.scrollLeft || left + link.offsetWidth > container.scrollLeft + container.clientWidth) {
      container.scrollTo({ left: Math.max(0, left - 16), behavior: "auto" });
    }
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
              <a href={`#${chapter.id}`} aria-current={active === chapter.id ? "location" : undefined}>
                {chapter.number && <small aria-hidden="true">{chapter.number}</small>}
                {chapter.label}
              </a>
            </li>
          ))}
        </ol>
        <div className="report-nav__end">
          {archived && latestHref && <a className="report-nav__latest" href={latestHref}>Latest edition →</a>}
          <a className={`report-nav__top${scrolled ? " is-visible" : ""}`} href="#top" aria-hidden={scrolled ? undefined : true} tabIndex={scrolled ? undefined : -1}>
            Top <span aria-hidden="true">↑</span>
          </a>
        </div>
      </div>
    </nav>
  );
}
