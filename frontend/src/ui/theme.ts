/** Colour theme choice: follow the operating system, or force light or dark (UX-01). */
export type ThemeChoice = "system" | "light" | "dark";

/** Also read by the inline script in index.html, which applies the choice before first paint. */
export const THEME_STORAGE_KEY = "labadda.theme";

/** The saved choice, or "system" when nothing valid is stored or storage is unavailable. */
export function readThemeChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

/** Show the page in the chosen theme without saving it. */
export function applyThemeChoice(choice: ThemeChoice): void {
  if (choice === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = choice;
}

/** Save the choice for this browser and apply it. Applying still works if storage is blocked. */
export function saveThemeChoice(choice: ThemeChoice): void {
  try {
    if (choice === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // Private browsing or blocked storage: the choice lasts for this page only.
  }
  applyThemeChoice(choice);
}
