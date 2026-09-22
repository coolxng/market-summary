// Privacy-conscious analytics hooks. Events go to Plausible only when the site
// is built with NEXT_PUBLIC_PLAUSIBLE_DOMAIN; otherwise every call is a no-op.
// Never pass personal data, watchlist contents or free text in props.

type Props = Record<string, string | number | boolean>;
type Plausible = (event: string, options?: { props?: Props }) => void;

export type AnalyticsEvent =
  | "Archive opened"
  | "Archived session opened"
  | "Asset page opened"
  | "Morning Tape opened"
  | "Watchlist updated"
  | "Calendar source click"
  | "Outbound source click";

export function track(event: AnalyticsEvent, props?: Props) {
  if (typeof window === "undefined") return;
  const plausible = (window as Window & { plausible?: Plausible }).plausible;
  if (typeof plausible === "function") plausible(event, props ? { props } : undefined);
}
