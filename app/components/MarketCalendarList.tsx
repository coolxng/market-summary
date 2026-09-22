import type { CalendarItem, MarketCalendar } from "../lib/report";
import { formatSessionDate } from "../lib/format";

function timeLabel(item: CalendarItem) {
  if (item.time) return item.time;
  if (item.time_status === "all_day") return "All day";
  if (item.time_status === "tentative") return "Tentative";
  return "Time not published";
}

function hasValues(item: CalendarItem) {
  return item.actual != null || item.consensus != null || item.previous != null;
}

function valueText(value: CalendarItem["actual"]) {
  return value == null || value === "" ? "—" : String(value);
}

function groupLabel(date: string, calendar: MarketCalendar, currentLabel: string) {
  const day = formatSessionDate(date, { weekday: "long", month: "short", day: "numeric" });
  if (calendar.window?.current_session === date) return `${currentLabel} · ${day}`;
  if (calendar.window?.next_session === date) return `Next session · ${day}`;
  return day;
}

export default function MarketCalendarList({
  calendar,
  currentLabel = "Current session",
  emptyNote,
}: {
  calendar: MarketCalendar | undefined;
  currentLabel?: string;
  emptyNote?: string;
}) {
  if (!calendar) {
    return <p className="data-empty">The market calendar was not captured for this issue. Later issues record scheduled events with their sources.</p>;
  }
  const unavailable = calendar.feeds.filter((feed) => feed.status === "unavailable");
  const dates = [...new Set(calendar.items.map((item) => item.date))];

  return (
    <div className="tape-calendar">
      {dates.length === 0 && (
        <p className="data-empty">
          {emptyNote ?? (unavailable.length
            ? "No scheduled events could be confirmed because calendar sources were unavailable at generation time."
            : "No scheduled U.S. releases, auctions, tracked earnings or market-structure dates were listed for this window.")}
        </p>
      )}
      {dates.map((date) => (
        <section className="tape-calendar__day" key={date} aria-label={groupLabel(date, calendar, currentLabel)}>
          <h3>{groupLabel(date, calendar, currentLabel)}</h3>
          <ol>
            {calendar.items.filter((item) => item.date === date).map((item, index) => (
              <li className="tape-calendar__row" key={`${item.title}-${index}`}>
                <div className="tape-calendar__time">
                  <strong>{timeLabel(item)}</strong>
                  {item.source_time && item.source_time_zone && <small>Source {item.source_time} {item.source_time_zone}</small>}
                </div>
                <div className="tape-calendar__event">
                  <strong>{item.title}</strong>
                  <p>
                    <span className="tape-chip">{item.category ?? "Scheduled"}</span>
                    {item.importance != null && <span className="tape-chip">Importance: {String(item.importance)} (source)</span>}
                    {item.rule_based && <span className="tape-chip tape-chip--muted">Rule-based</span>}
                    {item.date_status === "estimated_window" && <span className="tape-chip tape-chip--muted">Estimated date</span>}
                    {item.detail && <span>{item.detail}</span>}
                  </p>
                  {hasValues(item) && (
                    <dl className="tape-calendar__values">
                      <div><dt>Actual</dt><dd>{valueText(item.actual)}</dd></div>
                      <div><dt>Consensus</dt><dd>{valueText(item.consensus)}</dd></div>
                      <div><dt>Previous</dt><dd>{valueText(item.previous)}</dd></div>
                    </dl>
                  )}
                </div>
                <div className="tape-calendar__source">
                  {item.source_url
                    ? <a href={item.source_url} target="_blank" rel="noopener noreferrer" data-outbound="calendar">{item.source} ↗</a>
                    : <span>{item.source}</span>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}
      {unavailable.length > 0 && (
        <p className="feed-warning" role="note">
          Unavailable at generation: {unavailable.map((feed) => feed.name).join(", ")}. Events from those sources are omitted, not estimated.
        </p>
      )}
    </div>
  );
}
