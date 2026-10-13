// Calendar dates as whole days since 1970-01-01, so no time zone can shift them.
// The data's dates are plain "YYYY-MM-DD" strings (Pacific dates, like the store);
// they go in and out as strings and are only counted as days in between.

const DAY_MS = 86400000;

export function toDay(iso) {
  return Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / DAY_MS;
}

export function toIso(day) {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

export function makeDay(year, month, day) {
  return Date.UTC(year, month - 1, day) / DAY_MS;
}

export function parts(day) {
  const d = new Date(day * DAY_MS);
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
}

// Monday 0 to Sunday 6, like Python's date.weekday(); 1970-01-01 was a Thursday
export function weekday(day) {
  return (((day + 3) % 7) + 7) % 7;
}

// weeks run Monday to Sunday
export function weekStartDay(day) {
  return day - weekday(day);
}

export function weekStart(iso) {
  return toIso(weekStartDay(toDay(iso)));
}
