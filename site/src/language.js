// Shared with wyc79.github.io so one choice applies across the whole site.
export const LANGUAGE_KEY = "yc-lang";

const normalize = (language) => {
  const primary = String(language ?? "").toLowerCase().split("-")[0];
  return primary === "zh" ? "zh" : primary === "en" ? "en" : null;
};

export function selectLanguage(saved, preferred = []) {
  const stored = normalize(saved);
  if (stored) return stored;
  for (const language of preferred) {
    const supported = normalize(language);
    if (supported) return supported;
  }
  return "en";
}

function globalValue(name) {
  try {
    return globalThis[name];
  } catch {
    return null;
  }
}

const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

export function currentLanguage(options = {}) {
  const storage = hasOwn(options, "storage") ? options.storage : globalValue("localStorage");
  const navigator = hasOwn(options, "navigator") ? options.navigator : globalValue("navigator");
  let saved = null;
  try {
    saved = storage?.getItem(LANGUAGE_KEY);
  } catch {}
  const preferred = navigator?.languages?.length ? navigator.languages : navigator?.language ? [navigator.language] : [];
  return selectLanguage(saved, preferred);
}

export function changeLanguage(language, options = {}) {
  const storage = hasOwn(options, "storage") ? options.storage : globalValue("localStorage");
  const location = hasOwn(options, "location") ? options.location : globalValue("location");
  const next = normalize(language) ?? "en";
  try {
    storage?.setItem(LANGUAGE_KEY, next);
  } catch {}
  location?.reload();
}
