// The text of one week's game list (Competition ahead, a week opened). The games and
// their order come from lib/heatmap.js weekGames; this only formats them.

import { formatNumber } from "./count.js";
import { dateFormat } from "./format.js";
import { toDay } from "./lib/dates.js";
import { en } from "./strings.js";
import { formatDate } from "./heatview.js";

export const FIRST = 20; // month, quarter or year games listed before "Show all"

export function storeUrl(appid) {
  return `https://store.steampowered.com/app/${appid}/`;
}

// moved: weekGames' [kind, old date text, days since the change], or null
export function movedText(moved, s = en) {
  if (!moved) return null;
  const [kind, old, days] = moved;
  const ago = s.ahead.ago(days);
  return kind === "date_set" ? s.ahead.dateSet(ago) : s.ahead.moved(old, ago);
}

// hype_src "f" is a Games Popularity count, "r" an estimate from wishlist rank
export function followersText(followers, source, s = en) {
  if (followers == null) return null;
  const n = formatNumber(followers, s);
  return source === "r" ? s.ahead.followersEstimate(n) : s.ahead.followers(n);
}

// the game's date as the store gives it: "Oct 21", "Nov 2026", "Q4 2026", "2027"
export function dateText(game, s = en) {
  if (!game?.date) return null;
  const year = game.date.slice(0, 4);
  const month = +game.date.slice(5, 7);
  if (game.precision === "day") return formatDate(game.date, s);
  if (game.precision === "month") {
    const f = dateFormat(s.locale, { month: "short", year: "numeric" });
    return f.format(toDay(game.date) * 86400000);
  }
  if (game.precision === "quarter") return s.ahead.quarter(Math.ceil(month / 3), year);
  return year;
}

// list: weekGames' result; gameOf: appid -> the upcoming game (for its date)
export function detailItems(list, gameOf, s = en) {
  return list.map((g) => ({
    appid: g.appid,
    name: g.name || s.ahead.unnamed(g.appid),
    url: storeUrl(g.appid),
    part: g.layer, // exact, spread or year
    date: dateText(gameOf(g.appid), s),
    followers: followersText(g.followers, g.hype_src, s),
    moved: movedText(g.moved, s),
  }));
}

// The list in parts, exact dates first, each keeping weekGames' order:
// [{ part, heading: "Exact dates (3)", items, total }]. Exact dates are always
// listed in full; the other parts show FIRST games unless `open` has their part.
// Parts with no games are left out.
export function listParts(items, { year = false, open = new Set() } = {}, s = en) {
  const names = year ? ["exact", "spread", "year"] : ["exact", "spread"];
  return names
    .map((part) => {
      const all = items.filter((g) => g.part === part);
      const full = part === "exact" || open.has(part) || all.length <= FIRST;
      return {
        part,
        heading: s.ahead.listParts[part](formatNumber(all.length, s)),
        items: full ? all : all.slice(0, FIRST),
        total: all.length,
      };
    })
    .filter((p) => p.total > 0);
}
