"use client";

import { useEffect, useRef } from "react";
import type { NavLink } from "./SiteHeader";

// A native <details> disclosure keeps the menu usable before hydration; the
// client code only closes it after navigation or on Escape.
export default function MobileNav({ routes, reportLinks = [] }: { routes: NavLink[]; reportLinks?: NavLink[] }) {
  const ref = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && ref.current?.open) {
        ref.current.open = false;
        ref.current.querySelector("summary")?.focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  const shut = () => { if (ref.current) ref.current.open = false; };

  return (
    <details className="mobile-nav" ref={ref}>
      <summary aria-label="Open site menu">Menu</summary>
      <div className="mobile-nav__panel">
        <nav aria-label="Site (mobile)">
          <p className="mobile-nav__label">Go to page</p>
          {routes.map((link) => (
            <a key={link.href} href={link.href} aria-current={link.current ? "page" : undefined} onClick={shut}>
              {link.label}
            </a>
          ))}
        </nav>
        {reportLinks.length > 0 && (
          <nav aria-label="Report chapters (mobile)">
            <p className="mobile-nav__label">Jump within this report</p>
            {reportLinks.map((link) => (
              <a key={link.href} href={link.href} onClick={shut}><span aria-hidden="true">↓</span>{link.label}</a>
            ))}
          </nav>
        )}
      </div>
    </details>
  );
}
