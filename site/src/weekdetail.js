// The text of one week's game list (Competition ahead, a week opened), and the dates
// and links of the most anticipated list. The games and their order come from
// lib/heatmap.js weekGames and mostAnticipated; this only formats them.

import { formatNumber } from "./count.js";
import { en } from "./strings.js";
import { countText, formatDate } from "./heatview.js";

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

// the game's date as the store gives it: "10/21", "11/2026", "Q4 2026", "2027"
export function dateText(game, s = en) {
  if (!game?.date) return null;
  const year = game.date.slice(0, 4);
  const month = +game.date.slice(5, 7);
  if (game.precision === "day") return formatDate(game.date);
  if (game.precision === "month") return s.withYear(month, year);
  if (game.precision === "quarter") return s.ahead.quarter(Math.ceil(month / 3), year);
  return year;
}

// the date with its year included: "10/28/2026", "12/2026", "Q1 2027", "2027", or
// without one the store's own words ("Coming soon"), else "To be announced" (the
// most anticipated list)
export function steamDate(game, s = en) {
  if (!game?.date) return game?.date_text || s.ahead.tba;
  if (game.precision === "day") return fullDate(game.date, s);
  return dateText(game, s);
}

// "10/13/2026"; "2026/10/13" in Chinese
export function fullDate(iso, s = en) {
  return s.withYear(formatDate(iso), iso.slice(0, 4));
}

// tagPos: weekGames' or mostAnticipated's [tagid, place] list, count: the game's number
// of tags, names: tag id -> name. "Beat 'em up: tag 6 of 20 · Roguelike: tag 12 of 20";
// null when no tags are picked.
export function tagPosText(tagPos, count, names, s = en) {
  if (!tagPos?.length) return null;
  const of = formatNumber(count, s);
  return tagPos.map(([t, n]) => s.ahead.tagPos(names.get(t) ?? String(t), formatNumber(n, s), of)).join(s.bar.sep);
}

// list: weekGames' result; gameOf: appid -> the upcoming game (for its date);
// names: tag id -> name (for where the picked tags sit)
export function detailItems(list, gameOf, s = en, names = new Map()) {
  return list.map((g) => ({
    appid: g.appid,
    name: g.name || s.ahead.unnamed(g.appid),
    url: storeUrl(g.appid),
    part: g.layer, // exact, spread or year
    share: g.share, // what the game adds to the week: 1 for an exact date, a share for the rest
    date: dateText(gameOf(g.appid), s),
    followers: followersText(g.followers, g.hype_src, s),
    moved: movedText(g.moved, s),
    tagPos: tagPosText(g.tag_pos, g.tag_count, names, s),
  }));
}

// a name or a query for matching: lower case, accents dropped ("Pokémon" finds "pokemon")
export function fold(text) {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
}

// the games whose name holds the query (all of them for an empty query)
export function findGames(items, query) {
  const q = fold(query.trim());
  return q ? items.filter((g) => fold(g.name).includes(q)) : items;
}

// The list in parts, exact dates first, each keeping weekGames' order and listed in
// full (the page shows them in a scroll area with a search box):
// [{ part, heading, items, worth }]: "Exact dates (3)", or for month, quarter and year
// dates "Month or quarter dates (40, together about 3.2 games' worth)", worth being the
// sum of their shares (what the heatmap cell counts). Parts with no games are left out.
export function listParts(items, { year = false } = {}, s = en) {
  const names = year ? ["exact", "spread", "year"] : ["exact", "spread"];
  return names
    .map((part) => {
      const all = items.filter((g) => g.part === part);
      const worth = all.reduce((sum, g) => sum + (g.share ?? 1), 0);
      const n = formatNumber(all.length, s);
      const heading = s.ahead.listParts[part](n, countText(worth, s));
      return { part, heading, items: all, worth };
    })
    .filter((p) => p.items.length > 0);
}
