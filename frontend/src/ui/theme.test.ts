// @vitest-environment jsdom
import indexHtml from "../../index.html?raw";
import tokensCss from "./tokens.css?raw";
import { afterEach, describe, expect, it } from "vitest";
import { applyThemeChoice, readThemeChoice, saveThemeChoice, THEME_STORAGE_KEY } from "./theme";

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme choice", () => {
  it("defaults to the system theme", () => {
    expect(readThemeChoice()).toBe("system");
  });

  it("saves and applies an explicit choice", () => {
    saveThemeChoice("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(readThemeChoice()).toBe("dark");
  });

  it("returning to system clears the stored choice and the attribute", () => {
    saveThemeChoice("light");
    saveThemeChoice("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("ignores an invalid stored value", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "purple");
    expect(readThemeChoice()).toBe("system");
    applyThemeChoice(readThemeChoice());
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("uses the same storage key as the first-paint script in index.html", () => {
    expect(indexHtml).toContain(`localStorage.getItem("${THEME_STORAGE_KEY}")`);
  });
});

describe("design tokens", () => {
  const css = tokensCss;
  const block = (selector: string) => {
    const start = css.indexOf(selector);
    const open = css.indexOf("{", start);
    const close = css.indexOf("}", open);
    return css
      .slice(open + 1, close)
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("/*"));
  };

  it("defines the dark theme identically for the explicit choice and the system preference", () => {
    expect(block(':root[data-theme="dark"]')).toEqual(block(':root:not([data-theme="light"])'));
  });

  it("gives every dark token a light default", () => {
    const light = new Set(block(":root {").map((line) => line.split(":")[0]));
    for (const line of block(':root[data-theme="dark"]')) expect(light).toContain(line.split(":")[0]);
  });
});
