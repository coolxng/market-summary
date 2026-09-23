import type { ReactNode } from "react";

/** Site destinations for page footers, named to match the masthead. `root` is the relative path to the site root. */
export default function FooterLinks({ root, children }: { root: string; children?: ReactNode }) {
  return (
    <nav className="footer-nav" aria-label="Footer">
      <a href={root}>Today</a>
      <a href={`${root}morning/`}>Pre-Market</a>
      <a href={`${root}reports/`}>Archive</a>
      <a href={`${root}assets/`}>Assets</a>
      <a href={`${root}search/`}>Search</a>
      {children}
    </nav>
  );
}
