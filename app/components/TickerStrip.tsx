import { assetSummaries } from "../lib/assetSummary";

const STRIP = ["spx", "nasdaq", "dow", "vix", "us-10y", "bitcoin", "gold"];

/**
 * Slim scrolling band of headline markets from the latest issue. The list is
 * rendered twice so the loop is seamless; the copy is hidden from assistive
 * tech. It pauses on hover/focus and stands still for reduced motion.
 */
export default function TickerStrip({ root }: { root: string }) {
  const items = STRIP.map((slug) => assetSummaries.find((asset) => asset.slug === slug)).filter((asset) => asset && asset.price != null);
  if (!items.length) return null;
  const row = (copy: boolean) => (
    <ul className="ticker-strip__row" aria-hidden={copy || undefined}>
      {items.map((asset) => (
        <li key={asset!.slug}>
          <a href={`${root}assets/${asset!.slug}/`} tabIndex={copy ? -1 : undefined}>
            <span>{asset!.name}</span>
            <strong>{asset!.priceText}</strong>
            <b className={asset!.tone}>{asset!.changeText}</b>
          </a>
        </li>
      ))}
    </ul>
  );
  return (
    <nav className="ticker-strip" aria-label="Headline markets, latest close">
      <div className="ticker-strip__track">{row(false)}{row(true)}</div>
    </nav>
  );
}
