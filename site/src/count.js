// The top bar's match count, as text. The numbers come from lib/heatmap.js
// (matchCount for the counts, historyPanel for whether section 03 can show).

import { en } from "./strings.js";

export function formatNumber(n, s = en) {
  return new Intl.NumberFormat(s.locale).format(n);
}

// "1,204 of 20,495 upcoming", "3,950 of 82,910 past launches" and both joined,
// for the picked group (paid or free) of matchCount's result.
export function countLine(counts, group, s = en) {
  const f = (n) => formatNumber(n, s);
  const { upcoming, past } = counts[group];
  const parts = {
    upcoming: s.bar.upcoming(f(upcoming[0]), f(upcoming[1])),
    past: s.bar.past(f(past[0]), f(past[1])),
  };
  return { ...parts, text: parts.upcoming + s.bar.sep + parts.past };
}

// True when section 03 cannot show the history panel for this group: the panel's
// own rule, a quiet, normal or busy part with fewer than MIN_GROUP launches.
export function tooFewPast(panel, group) {
  return !panel[group].shown;
}

// The phone's one-line summary: "3 tags · Paid · 1,204 upcoming" (upcoming games
// of the picked group, as in the count line).
export function summaryLine(st, counts, s = en) {
  return [
    s.bar.summaryTags(st.tags.length),
    s.bar[st.group],
    s.bar.summaryUpcoming(formatNumber(counts[st.group].upcoming[0], s)),
  ].join(s.bar.sep);
}
