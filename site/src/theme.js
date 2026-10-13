// Light or dark: the system setting until the user picks one, which is kept in
// localStorage (the inline script in the page head applies it before first paint,
// with the same key). Storage can be blocked, so every access is guarded.

export const THEME_KEY = "slw-theme";
const dark = () => window.matchMedia("(prefers-color-scheme: dark)");

export function currentTheme() {
  return document.documentElement.dataset.theme || (dark().matches ? "dark" : "light");
}

export function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(THEME_KEY, t);
  } catch {
    // not remembered, still applied
  }
}

// calls `fn` with the theme in use now and whenever the system setting changes it
export function onThemeChange(fn) {
  fn(currentTheme());
  dark().addEventListener("change", () => fn(currentTheme()));
}
