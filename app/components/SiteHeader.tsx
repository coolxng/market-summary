import ThemeToggle from "./ThemeToggle";
import MobileNav from "./MobileNav";
import HeaderSearch from "./HeaderSearch";

export type SiteSection = "close" | "morning" | "reports" | "search" | "asset";

export type NavLink = { href: string; label: string; current?: boolean };

/**
 * Shared masthead for every route. `root` is the relative path back to the site
 * root ("./", "../", "../../") so links stay correct under the GitHub Pages
 * base path and in local dev without one.
 *
 * The masthead only carries site-level destinations (links that change the
 * page). In-report chapter links live in the separate ReportNav bar, so the two
 * never mix; `reportLinks` only feeds the mobile menu's second group.
 */
export default function SiteHeader({
  root,
  current,
  reportLinks = [],
  slashShortcut = true,
}: {
  root: string;
  current: SiteSection;
  reportLinks?: NavLink[];
  /** False on pages whose own filter box already owns "/"; the bar then answers only to Ctrl/Cmd+K. */
  slashShortcut?: boolean;
}) {
  const routes: NavLink[] = [
    { href: root, label: "Today", current: current === "close" },
    { href: `${root}morning/`, label: "Pre-Market", current: current === "morning" },
    { href: `${root}reports/`, label: "Archive", current: current === "reports" },
    { href: `${root}assets/`, label: "Assets", current: current === "asset" },
  ];
  const searchRoute: NavLink = {
    href: `${root}search/`,
    label: "Search",
    current: current === "search",
  };

  return (
    <header className="site-header">
      <a className="brand" href={root} aria-label="The Daily Tape home">
        <span className="brand-mark" style={{ backgroundImage: `url("${root}logo.png")` }} aria-hidden="true" />
        <span>THE DAILY TAPE</span>
      </a>
      <nav className="site-nav" aria-label="Site">
        {routes.map((link) => (
          <a key={link.href} href={link.href} aria-current={link.current ? "page" : undefined}>{link.label}</a>
        ))}
      </nav>
      {/* The search page has its own large search box, so the masthead bar would only duplicate it. */}
      {current !== "search" && <HeaderSearch root={root} slashShortcut={slashShortcut} />}
      <div className="site-header__tools">
        <MobileNav routes={[...routes, searchRoute]} reportLinks={reportLinks} />
        <ThemeToggle />
      </div>
    </header>
  );
}
