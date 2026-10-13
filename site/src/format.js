// Intl formatters, made once per locale and options: building one costs far more
// than using it, and the heatmap formats hundreds of numbers per draw.

const cache = new Map();

function cached(Kind, locale, options) {
  const key = `${Kind.name} ${locale} ${JSON.stringify(options)}`;
  let f = cache.get(key);
  if (!f) {
    f = new Kind(locale, options);
    cache.set(key, f);
  }
  return f;
}

export const numberFormat = (locale, options = {}) => cached(Intl.NumberFormat, locale, options);

// dates here are whole UTC days (lib/dates.js), so they are formatted in UTC
export const dateFormat = (locale, options = {}) => cached(Intl.DateTimeFormat, locale, { ...options, timeZone: "UTC" });
