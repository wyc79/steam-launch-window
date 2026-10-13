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
    raw: "Raw counts",
    rawHint: "Plain counts instead of a comparison with a usual week, in sections 01 and 03",
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

  // What history says: the panel and the model's lines
  history: {
    panelTitle: "Quiet, normal and busy weeks",
    panelFor: (group, n) => `${group} games like yours: ${n} past launches with a 30-day review count.`,
    panelForAll: (group, n) => `All ${group} games: ${n} past launches with a 30-day review count.`,
    caption: "30-day reviews of past launches, by how busy their launch week was",
    heads: { part: "Launch week", p75: "75th percentile", p90: "90th percentile", median: "Median", games: "Launches" },
    headsShort: { p75: "75th", p90: "90th", median: "Median", games: "Launches" },
    parts: { quiet: "Quiet", normal: "Normal", busy: "Busy" },
    range: (lo, hi) => (lo === hi ? lo : `${lo} to ${hi}`),
    read: "About 1 in 4 launches got more reviews than the 75th percentile, about 1 in 10 more than the 90th.",
    barsKey: "Bars: solid to the 75th, faint to the 90th, a gap at the median.",
    cutsRelative: (quiet, busy) =>
      `Busy: other launches like yours that week, against the average week in the 13 weeks before. Quiet is up to ${quiet} times that, busy over ${busy}.`,
    cutsRaw: (quiet, busy) => `Busy: how many other launches like yours that week. Quiet is up to ${quiet}, busy over ${busy}.`,
    none: "No past launches match. Try fewer tags or Any of these.",
    tooFew: (min) =>
      `Too few past launches to split into quiet, normal and busy weeks (each needs ${min}). Try fewer tags or Any of these.`,
    timingTitle: "Launch timing",
    timingFor: (group) => `${group} games, compared with otherwise similar launches:`,
    notReady: "Not ready yet.",
    // a rate ratio as words: "37% fewer reviews (24% to 47% fewer)"
    change: (pct, dir, lo, hi) => `${pct} ${dir} reviews (${lo} to ${hi} ${dir})`,
    fewer: "fewer",
    more: "more",
    noEffect: (what) => `${what}: no clear effect.`,
    // advice: the range leaves out 1.0 and, where the model ran one, the chance test agrees
    sale: "Steam seasonal sales",
    saleAvoid: (change) => `Avoid launching during a Steam seasonal sale: such launches got ${change}.`,
    saleGood: (change) => `Launches during a Steam seasonal sale got ${change}.`,
    fest: "Themed fests for your tags",
    festAvoid: (change) => `Avoid a themed fest that matches your tags: such launches got ${change}.`,
    festGood: (change) => `Launches during a themed fest that matched their tags got ${change}.`,
    holidays: {
      us_thanksgiving: (change, years) => `Avoid US Thanksgiving to Cyber Monday: in ${years} years, such launches got ${change}.`,
      xmas_newyear: (change, years) => `Avoid Christmas to New Year: in ${years} years, such launches got ${change}.`,
    },
    holidaysGood: {
      us_thanksgiving: (change, years) => `In ${years} years, launches from US Thanksgiving to Cyber Monday got ${change}.`,
      xmas_newyear: (change, years) => `In ${years} years, launches from Christmas to New Year got ${change}.`,
    },
    // the range leaves out 1.0 but the chance test does not confirm it: not advice
    names: {
      sale: "Steam seasonal sales",
      themed_fest: "Themed fests for your tags",
      us_thanksgiving: "US Thanksgiving to Cyber Monday",
      xmas_newyear: "Christmas to New Year",
    },
    years: (n) => ` (${n} years)`,
    unconfirmed: (name, dir, years, also) =>
      `${name}: ${dir} reviews in past years${years}, not confirmed by a chance test${also ? `; ${also}` : ""}.`,
    also: {
      us_thanksgiving: "the week also falls in Steam's Autumn Sale most years",
      xmas_newyear: "the week also falls in Steam's Winter Sale every year",
    },
    demoFest: "A demo out before Next Fest",
    demoAdvice: "If you have a demo, have it out before Next Fest.",
    demoVsAfter: (change) =>
      `Launches whose demo was out by the last Next Fest got ${change} than those whose demo came out after it`,
    demoVsNone: (change) => `${change} than launches with no demo`,
    demoAsNone: "no clear difference from launches with no demo",
    cautious: " (a cautious range)",
    demoAfter: (change) => `A demo that came out after the last Next Fest went with ${change} than no demo.`,
    // weekly competition: described from the fit with the placebo, never a predicted penalty
    competition: "Weekly competition",
    crowdAtMost: "small at most; much of it is general crowding",
    crowdPart: "small; part of it is general crowding",
    crowdNone: (dir) => `launches in busier weeks of their niche got ${dir} reviews`,
    niche: {
      comp_tier: "a niche here is games with similar tags, a shared language and the same price tier, not just your tags",
      competition: "a niche here is games with similar tags and a shared language, not just your tags",
    },
    competitionLine: (desc, niche) => `Weekly competition: ${desc} (${niche}).`,
    china: (fewer, both, overlapped) =>
      fewer
        ? `China holidays (unconfirmed): launches during Spring Festival and National Day got fewer reviews in past years${both ? ", with or without Simplified Chinese" : ""}${overlapped ? ", and every one overlapped a Steam sale or fest" : ""}.`
        : "China holidays (unconfirmed): no clear pattern in past launches.",
    caveat: "These are patterns in past launches, not proof of cause.",
  },

  // Typical for this time of year: the seasonal outlook
  season: {
    key: "1.0 = as many launches as the average week in the 13 weeks before. The bar: the usual value. The box behind it: the typical spread across years.",
    good: "Quiet is not the same as good.",
    from: (group) => `From all ${group} games in your languages, not just your tags.`,
    paid: "paid",
    free: "free",
    label: "The next 26 weeks, how busy each usually is",
    none: "n/a",
    noneSaid: "not enough past years",
    spread: (lo, hi) => `typical spread across years ${lo} to ${hi}`,
    usually: (v) => `usually ${v}`,
    calendar: "the same week in past years",
    at: (name) => `the week of ${name}`,
    after: (n, name) => (n === 1 ? `1 week after ${name}` : `${n} weeks after ${name}`),
    before: (n, name) => (n === 1 ? `1 week before ${name}` : `${n} weeks before ${name}`),
    drivers: (list) => `From ${list}.`,
    unconfirmed: "unconfirmed",
    detail: (week, value, spread) => (spread ? `${week}: ${value} (${spread}).` : `${week}: ${value}.`),
    option: (week, value, spread, drivers) =>
      `${week}: ${value}${spread ? `, ${spread}` : ""}.${drivers ? ` ${drivers}` : ""}`,
    eventsFailed: "Steam events could not be loaded, so this pattern leaves them out.",
  },

  // Competition ahead: the niche trend line
  trend: {
    line: (row, ratio) => `${row} is ${ratio}x as large a share of upcoming games (exact dates) as of last year's launches.`,
    caveat: "Announced games: not all will launch.",
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
