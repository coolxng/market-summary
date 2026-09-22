"use client";

import { useEffect, useRef } from "react";

type NavLink = { href: string; label: string; current?: boolean };

// A native <details> disclosure keeps the menu usable before hydration; the
// client code only closes it after navigation or on Escape.
export default function MobileNav({ links }: { links: NavLink[] }) {
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

  return (
    <details className="mobile-nav" ref={ref}>
      <summary aria-label="Open site menu">Menu</summary>
      <nav aria-label="Mobile">
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            aria-current={link.current ? "page" : undefined}
            onClick={() => { if (ref.current) ref.current.open = false; }}
          >
            {link.label}
          </a>
        ))}
      </nav>
    </details>
  );
}
