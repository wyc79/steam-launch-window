// Every piece of text the site shows. English now; Chinese comes later as a
// second object with the same keys. Functions take numbers already formatted.

export const en = {
  lang: "en",
  locale: "en-US",

  title: "Steam Launch Window",
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
  },

  hero: {
    title: "Steam launch window",
    lede: "Pick your game's Steam tags. See how crowded the coming weeks are, and how similar games did when they launched.",
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
    fewPast: "Too few past launches for section 03.",
  },

  sections: {
    ahead: {
      num: "01",
      title: "Competition ahead",
      intro: "Games in your niche with dates in each of the next 26 weeks.",
    },
    season: {
      num: "02",
      title: "Typical for this time of year",
      intro: "How busy each of those weeks usually is, from past years' launches.",
    },
    history: {
      num: "03",
      title: "What history says",
      intro: "How similar past launches did in quiet, normal and busy weeks, and around sales and fests.",
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
