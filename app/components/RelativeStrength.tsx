import type { RelativeStrengthRow } from "../lib/report";
import { assetBySymbol } from "../lib/assets";
import { formatPp, toneClass } from "../lib/format";

const PERSISTENCE_LABEL: Record<RelativeStrengthRow["persistence"], string> = {
  leading: "Leading",
  lagging: "Lagging",
  mixed: "Mixed",
  incomplete: "Incomplete",
};

function Table({ title, rows, assetBaseHref }: { title: string; rows: RelativeStrengthRow[]; assetBaseHref: string }) {
  const sorted = [...rows].sort((a, b) => (b["1m"] ?? -Infinity) - (a["1m"] ?? -Infinity));
  return (
    <table className="rs-table">
      <caption>{title}</caption>
      <thead>
        <tr><th scope="col">Name</th><th scope="col">1D</th><th scope="col">5D</th><th scope="col">1M</th><th scope="col">Trend</th></tr>
      </thead>
      <tbody>
        {sorted.map((row) => {
          const asset = assetBySymbol[row.symbol];
          return (
            <tr key={row.symbol}>
              <th scope="row">{asset ? <a href={`${assetBaseHref}${asset.slug}/`}>{row.name}</a> : row.name}<small>{row.symbol}</small></th>
              {(["1d", "5d", "1m"] as const).map((window) => <td key={window} className={toneClass(row[window])}>{formatPp(row[window])}</td>)}
              <td><span className={`rs-tag rs-tag--${row.persistence}`}>{PERSISTENCE_LABEL[row.persistence]}</span></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** Performance relative to SPY over 1D/5D/1M, to separate persistent leaders from one-day winners. */
export default function RelativeStrength({ rows, assetBaseHref }: { rows: RelativeStrengthRow[] | undefined; assetBaseHref: string }) {
  if (!rows?.length) return null;
  return (
    <div className="relative-strength-block">
      <div className="subsection-head"><span>RELATIVE STRENGTH VS SPY</span><small>PERCENTAGE POINTS OF TOTAL RETURN · LEADING = AHEAD OF SPY IN ALL THREE WINDOWS</small></div>
      <div className="rs-grid">
        <Table title="Sector ETFs" rows={rows.filter((row) => row.group === "Sector")} assetBaseHref={assetBaseHref} />
        <Table title="Tracked large caps" rows={rows.filter((row) => row.group === "Large cap")} assetBaseHref={assetBaseHref} />
      </div>
    </div>
  );
}
