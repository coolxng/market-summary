import ThemeToggle from "./ThemeToggle";
import MobileNav from "./MobileNav";

export type SiteSection = "close" | "morning" | "reports" | "search" | "asset";

type NavLink = { href: string; label: string; current?: boolean };

/**
 * Shared masthead for every route. `root` is the relative path back to the site
 * root ("./", "../", "../../") so links stay correct under the GitHub Pages
 * base path and in local dev without one.
 */
export default function SiteHeader({
  root,
  current,
  sectionLinks = [],
}: {
  root: string;
  current: SiteSection;
  sectionLinks?: Array<[id: string, label: string]>;
}) {
  const routes: NavLink[] = [
    { href: root, label: "Close", current: current === "close" },
    { href: `${root}morning/`, label: "Morning", current: current === "morning" },
    { href: `${root}reports/`, label: "Archive", current: current === "reports" },
    { href: `${root}search/`, label: "Search", current: current === "search" },
  ];
  const anchors: NavLink[] = sectionLinks.map(([id, label]) => ({ href: `#${id}`, label }));
  const links = [...anchors, ...routes.filter((route) => !(anchors.length && route.current))];

  return (
    <header className="site-header">
      <a className="brand" href={root} aria-label="The Daily Tape home">
        <span className="brand-mark" style={{ backgroundImage: `url("${root}logo.png")` }} aria-hidden="true" />
        <span>THE DAILY TAPE</span>
      </a>
      <nav className="site-nav" aria-label="Primary">
        {links.map((link) => (
          <a key={link.href} href={link.href} aria-current={link.current ? "page" : undefined}>{link.label}</a>
        ))}
      </nav>
      <div className="site-header__tools">
        <MobileNav links={links} />
        <ThemeToggle />
      </div>
    </header>
  );
}
