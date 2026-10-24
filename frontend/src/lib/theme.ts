import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "aquasense-theme";

function currentTheme(): Theme {
  return document.documentElement.dataset["theme"] === "dark" ? "dark" : "light";
}

/** Theme state synced with <html data-theme>. index.html sets the initial value before paint. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document === "undefined" ? "light" : currentTheme(),
  );

  useEffect(() => {
    document.documentElement.dataset["theme"] = theme;
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Storage can be unavailable (private mode); the theme still applies for this visit.
    }
  }, [theme]);

  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

/**
 * Resolves CSS custom properties to concrete colours for canvas drawing,
 * re-reading them whenever the theme attribute changes.
 */
export function useCssColors<K extends string>(names: readonly K[]): Record<K, string> {
  const read = () => {
    const style = getComputedStyle(document.documentElement);
    return Object.fromEntries(
      names.map((n) => [n, style.getPropertyValue(`--${n}`).trim()]),
    ) as Record<K, string>;
  };
  const [colors, setColors] = useState<Record<K, string>>(read);

  useEffect(() => {
    const observer = new MutationObserver(() => setColors(read()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
    // names is a constant tuple at every call site
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return colors;
}
