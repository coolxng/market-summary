// Publication schedule helpers. The Close Tape publishes 30 minutes after the
// U.S. close (3:30 PM America/Chicago) on NYSE trading days.

type CalendarDate = { year: number; month: number; day: number };
export type PublicationIndicator = {
  mode: "countdown" | "building" | "published";
  label: string;
  value: string;
  meta: string;
};

const CENTRAL_TIME_ZONE = "America/Chicago";
const PUBLISH_HOUR = 15;
const PUBLISH_MINUTE = 30;
const RECENT_PUBLISH_WINDOW_MINUTES = 90;

export function calendarKey({ year, month, day }: CalendarDate) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function centralCalendarDate(value: Date): CalendarDate {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: CENTRAL_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return { year: Number(values.year), month: Number(values.month), day: Number(values.day) };
}

function addCalendarDays(value: CalendarDate, amount: number): CalendarDate {
  const date = new Date(Date.UTC(value.year, value.month - 1, value.day + amount));
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1, day: date.getUTCDate() };
}

function calendarWeekday(value: CalendarDate) {
  return new Date(Date.UTC(value.year, value.month - 1, value.day)).getUTCDay();
}

function nthWeekdayOfMonth(year: number, month: number, weekday: number, occurrence: number): CalendarDate {
  const firstWeekday = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
  const day = 1 + ((weekday - firstWeekday + 7) % 7) + ((occurrence - 1) * 7);
  return { year, month, day };
}

function lastWeekdayOfMonth(year: number, month: number, weekday: number): CalendarDate {
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const lastWeekday = new Date(Date.UTC(year, month - 1, lastDay)).getUTCDay();
  return { year, month, day: lastDay - ((lastWeekday - weekday + 7) % 7) };
}

function observedFixedHoliday(year: number, month: number, day: number): CalendarDate {
  const date = { year, month, day };
  const weekday = calendarWeekday(date);
  if (weekday === 6) return addCalendarDays(date, -1);
  if (weekday === 0) return addCalendarDays(date, 1);
  return date;
}

function easterSunday(year: number): CalendarDate {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = ((19 * a) + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + (2 * e) + (2 * i) - h - k) % 7;
  const m = Math.floor((a + (11 * h) + (22 * l)) / 451);
  const month = Math.floor((h + l - (7 * m) + 114) / 31);
  const day = ((h + l - (7 * m) + 114) % 31) + 1;
  return { year, month, day };
}

function marketHolidayKeys(year: number) {
  const holidays = new Set<string>();
  const add = (value: CalendarDate) => holidays.add(calendarKey(value));

  const newYearsDay = { year, month: 1, day: 1 };
  const newYearsWeekday = calendarWeekday(newYearsDay);
  if (newYearsWeekday !== 6) add(newYearsWeekday === 0 ? addCalendarDays(newYearsDay, 1) : newYearsDay);

  add(nthWeekdayOfMonth(year, 1, 1, 3));
  add(nthWeekdayOfMonth(year, 2, 1, 3));
  add(addCalendarDays(easterSunday(year), -2));
  add(lastWeekdayOfMonth(year, 5, 1));
  add(observedFixedHoliday(year, 6, 19));
  add(observedFixedHoliday(year, 7, 4));
  add(nthWeekdayOfMonth(year, 9, 1, 1));
  add(nthWeekdayOfMonth(year, 11, 4, 4));
  add(observedFixedHoliday(year, 12, 25));

  return holidays;
}

export function isTradingDay(value: CalendarDate) {
  const weekday = calendarWeekday(value);
  if (weekday === 0 || weekday === 6) return false;
  const key = calendarKey(value);
  return [value.year - 1, value.year, value.year + 1].every((year) => !marketHolidayKeys(year).has(key));
}

function centralDateTime(value: CalendarDate, hour: number, minute: number) {
  const guess = Date.UTC(value.year, value.month - 1, value.day, hour, minute);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: CENTRAL_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date(guess));
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const zonedAsUtc = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second),
  );
  const offset = zonedAsUtc - guess;
  return new Date(guess - offset);
}

/** Next NYSE trading day at `hour:minute` Central that is still in the future. */
export function nextTradingDayAt(now: Date, hour: number, minute: number) {
  let candidate = centralCalendarDate(now);
  for (let index = 0; index < 14; index += 1) {
    if (isTradingDay(candidate)) {
      const target = centralDateTime(candidate, hour, minute);
      if (target.getTime() > now.getTime()) return target;
    }
    candidate = addCalendarDays(candidate, 1);
  }
  return centralDateTime(addCalendarDays(candidate, 1), hour, minute);
}

function publicationTarget(value: CalendarDate) {
  return centralDateTime(value, PUBLISH_HOUR, PUBLISH_MINUTE);
}

function nextPublication(now: Date) {
  return nextTradingDayAt(now, PUBLISH_HOUR, PUBLISH_MINUTE);
}

function relativePublicationName(now: Date, target: Date) {
  const today = centralCalendarDate(now);
  const targetDate = centralCalendarDate(target);
  const tomorrow = addCalendarDays(today, 1);
  if (calendarKey(targetDate) === calendarKey(tomorrow)) return "TOMORROW";
  return new Intl.DateTimeFormat("en-US", { timeZone: CENTRAL_TIME_ZONE, weekday: "long" }).format(target).toUpperCase();
}

function countdownValue(now: Date, target: Date) {
  const minutes = Math.max(0, Math.ceil((target.getTime() - now.getTime()) / 60000));
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours >= 24) return relativePublicationName(now, target);
  if (hours === 0) return `${remainder}M`;
  return `${hours}H ${String(remainder).padStart(2, "0")}M`;
}

export function getPublicationIndicator(now: Date, sessionDate: string, generatedAt: Date): PublicationIndicator {
  const today = centralCalendarDate(now);
  const todayKey = calendarKey(today);
  const tradingToday = isTradingDay(today);
  const todayTarget = tradingToday ? publicationTarget(today) : null;
  const publishedToday = sessionDate === todayKey;
  const generatedTime = generatedAt.getTime();
  const minutesSincePublished = Number.isFinite(generatedTime)
    ? Math.floor((now.getTime() - generatedTime) / 60000)
    : Number.POSITIVE_INFINITY;

  if (publishedToday && minutesSincePublished >= 0 && minutesSincePublished <= RECENT_PUBLISH_WINDOW_MINUTES) {
    const nextTarget = nextPublication(now);
    return {
      mode: "published",
      label: "JUST PUBLISHED",
      value: minutesSincePublished < 1 ? "UPDATED NOW" : `UPDATED ${minutesSincePublished}M AGO`,
      meta: `Next issue ${relativePublicationName(now, nextTarget).toLowerCase()} · 30 min after U.S. market close`,
    };
  }

  if (todayTarget && now.getTime() >= todayTarget.getTime() && !publishedToday) {
    return {
      mode: "building",
      label: "PREPARING TODAY'S ISSUE",
      value: "IN PROGRESS",
      meta: "Publishing now",
    };
  }

  const nextTarget = nextPublication(now);
  return {
    mode: "countdown",
    label: "NEXT ISSUE IN",
    value: countdownValue(now, nextTarget),
    meta: "30 min after U.S. market close",
  };
}
