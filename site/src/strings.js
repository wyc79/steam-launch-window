// Every piece of text the site shows. English now; Chinese comes later as a
// second object with the same keys. Functions take numbers already formatted.

export const en = {
  lang: "en",
  locale: "en-US",

  title: "Steam Launch Window",
  pageTitle: (page, site) => `${page} · ${site}`, // a page other than the tool
  description:
    "Pick a Steam launch week: how crowded the coming weeks are for your tags, and how similar games did when they launched.",

  mast: {
    name: "Steam Launch Window",
    by: "By Yuanchen Wang",
    sealAlt: "Yuanchen Wang: back to the main site",
    methods: "Methods",
    source: "GitHub",
    theme: "Dark theme",
    light: "Light",
    dark: "Dark",
    // under the masthead, in place of a big title
    lede: "Pick your game's Steam tags. See how similar games did when they launched, and how crowded the coming weeks are.",
    caveat: "Reviews stand in for sales. Patterns, not promises.",
  },

  bar: {
    label: "Your game",
    tags: "Tags",
    tagPlaceholder: "Type a Steam tag",
    tagLoading: "Loading tags…",
    tagNone: "No tag matches",
    tagUpcoming: (n) => `${n} upcoming`,
    removeTag: (name) => `Remove ${name}`,
    mode: "Match",
    and: "All of these",
    or: "Any of these",
    languages: "Languages",
    anyLanguage: "Any language",
    nLanguages: (n) => `${n} languages`,
    price: "Price",
    paid: "Paid",
    free: "Free",
    loading: "Loading data…",
    error: "Could not load the data. Reload the page to try again.",
    upcoming: (n, total) => `${n} of ${total} upcoming`,
    past: (n, total) => `${n} of ${total} past launches`,
    sep: " · ",
    fewPast: (num) => `Too few for section ${num}.`, // num: the history section's number
    // the one-line bar that stays on top on phones, where the controls scroll away
    summaryTags: (n) => (n === 0 ? "All tags" : n === 1 ? "1 tag" : `${n} tags`),
    summaryUpcoming: (n) => `${n} upcoming`,
    summaryLabel: (line) => `${line}. Back to the controls`,
  },

  // Competition ahead: the heatmap
  ahead: {
    allGames: "All games",
    combo: { and: "All of these", or: "Any of these" },
    typical: (n) => `about ${n} launches in a typical week`,
    // a row with under one launch in a typical week shows plain counts
    fewLaunches: (n) =>
      `counts: ${n === 0 ? "no launches" : n === 1 ? "only 1 launch" : `only ${n} launches`} in the last year`,
    // the parts of each week, as short labels, single letters (phones) and in full for screen readers
    parts: { exact: "Exact", spread: "Spread", year: "Year" },
    partsShort: { exact: "E", spread: "S", year: "Y" },
    partNames: { exact: "exact dates", spread: "month or quarter dates", year: "year only" },
    corner: "Week of",
    thisWeek: "This week",
    far: "Dates still being set",
    raw: "Raw counts",
    yearLayer: "Show games without a firm date",
    scaleNormal: "1.0 = as many as a typical week. 2.0 = twice as many.",
    scaleRaw: "Numbers are games. Shades still compare with a typical week.",
    key: "Each week: exact dates on top (E), month and quarter dates spread below (S).",
    keyYear: "Hatched (Y): games dated only by year, spread over the weeks left in that year.",
    typicalNote: "A typical week is the row's average week of real launches over the last 52 weeks.",
    countsNote: "Rows marked counts had too few past launches to compare with: they show games, unshaded.",
    caveatNear: "Near weeks run high: some of these dates will slip.",
    caveatFar: "Far weeks run low: many dates are not set yet.",
    caveatYear: "The year-only layer is a spread, not real dates.",
    games: (n, count) => (count === 1 ? `${n} game` : `${n} games`),
    below: (v) => `<${v}`, // a value too small to show as 0.1
    under: (v) => `under ${v}`, // the same, read aloud
    sometimeFor: (row) => `${row}, dated only by year:`,
    sometime: (year, games) => `sometime in ${year}: ${games}`,
    later: (games) => `later: ${games}`,
    noSometime: "no games dated only by year.",
    empty: "No upcoming games match. Try fewer tags, Any of these, or more languages.",
    emptyCombo: "No upcoming games have all of these tags. The rows show each tag alone.",
    eventsFailed: "Steam events could not be loaded, so the events lanes are missing.",
    // one cell, for screen readers
    cell: (row, week, parts) => `${row}, week of ${week}: ${parts}`,
    cellPart: (name, value) => `${name} ${value}`,
    unitNormal: "(1.0 = as many as a typical week)",
    unitRaw: "games",
    events: (list) => `Events: ${list}`,
    // the events lanes
    eventsLabel: "Events",
    kinds: {
      seasonal_sale: "Steam sales",
      next_fest: "Next Fest",
      themed_fest: "Themed fests",
      cn_holiday: "China holidays",
    },
    unconfirmed: "unconfirmed",
    estimate: "date estimated",
    eventName: (name, note) => (note ? `${name} (${note})` : name),
    eventDates: (from, to) => `${from} to ${to}`,
    // the week detail
    hint: "Pick a week to see its games.",
    week: (from, to) => `Week of ${from} to ${to}`,
    detailFor: (row, group) => `${row}, ${group}`,
    detailCount: (games) => `${games} in this week.`,
    detailNone: "No games in this week.",
    detailEvents: "Events",
    // the week's list, in parts: exact dates always shown in full
    listParts: {
      exact: (n) => `Exact dates (${n})`,
      spread: (n) => `Month or quarter dates (${n})`,
      year: (n) => `Year only (${n})`,
    },
    announce: (row, week, count) => `${row}, ${week}. ${count}`,
    quarter: (q, year) => `Q${q} ${year}`,
    followers: (n) => `${n} followers`,
    followersEstimate: (n) => `about ${n} followers, estimated from wishlist rank`,
    moved: (old, ago) => `moved here from ${old}, ${ago}`,
    dateSet: (ago) => `date just set, ${ago}`,
    ago: (days) => (days <= 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`),
    unnamed: (appid) => `App ${appid}`,
    showAll: (n) => `Show all ${n}`,
  },

  // numbered in page order (ui/sections.js SECTIONS)
  sections: {
    history: {
      title: "What history says",
      intro: "How similar past launches did in quiet, normal and busy weeks, and around sales and fests.",
    },
    season: {
      title: "Typical for this time of year",
      intro: "How busy each of the coming 26 weeks usually is, from past years' launches.",
    },
    ahead: {
      title: "Competition ahead",
      intro: "Games in your niche with dates in each of the next 13 weeks.",
    },
  },

  footer: {
    data: "Data",
    steam: "Steam",
    steamNote: " (public store pages, daily)",
    gp: "Games Popularity",
    gpNote: " (follower counts)",
    hf: "the dataset on Hugging Face",
    hfNote: ". ",
    asOf: (date) => `Snapshot of ${date}.`,
    methods: "Methods",
    source: "Source on GitHub",
    affiliation: "Not affiliated with Valve.",
  },

  methods: {
    title: "Methods",
    soon: "This page is being written. Until then, the methods are in the repository:",
    link: "docs/methods.md",
    back: "Back to the tool",
  },

  // Steam's language codes; codes without a name here (extraN, langNN) are not offered
  languages: {
    english: "English",
    schinese: "Simplified Chinese",
    tchinese: "Traditional Chinese",
    japanese: "Japanese",
    korean: "Korean",
    german: "German",
    french: "French",
    spanish: "Spanish (Spain)",
    latam: "Spanish (Latin America)",
    portuguese: "Portuguese (Portugal)",
    brazilian: "Portuguese (Brazil)",
    russian: "Russian",
    italian: "Italian",
    polish: "Polish",
    turkish: "Turkish",
    ukrainian: "Ukrainian",
    czech: "Czech",
    dutch: "Dutch",
    hungarian: "Hungarian",
    thai: "Thai",
    vietnamese: "Vietnamese",
    arabic: "Arabic",
    swedish: "Swedish",
    danish: "Danish",
    finnish: "Finnish",
    norwegian: "Norwegian",
    greek: "Greek",
    romanian: "Romanian",
    bulgarian: "Bulgarian",
    indonesian: "Indonesian",
  },
};

export const strings = en;
