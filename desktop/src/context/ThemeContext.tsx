import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from "react";

export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export interface ThemeContextValue {
  theme: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = "hitl_theme";

const getSystemTheme = (): ResolvedTheme => {
  if (typeof window !== "undefined" && window.matchMedia) {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    } catch {
      return "light";
    }
  }
  return "light";
};

const getSavedTheme = (): ThemeMode => {
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "light" || saved === "dark" || saved === "system") {
        return saved;
      }
    } catch {
      // Fallback
    }
  }
  return "system";
};

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: ThemeMode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({
  children,
  defaultTheme,
}) => {
  const [theme, setThemeState] = useState<ThemeMode>(() => defaultTheme || getSavedTheme());
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme);

  // Listen to system preference changes
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;

    try {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = (e: MediaQueryListEvent | MediaQueryList) => {
        setSystemTheme(e.matches ? "dark" : "light");
      };

      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener("change", handler);
        return () => mediaQuery.removeEventListener("change", handler);
      } else if ("addListener" in mediaQuery) {
        (mediaQuery as any).addListener(handler);
        return () => (mediaQuery as any).removeListener(handler);
      }
    } catch {
      // Ignore media query errors in test/restricted environments
    }
  }, []);

  const resolvedTheme: ResolvedTheme = useMemo(() => {
    if (theme === "system") {
      return systemTheme;
    }
    return theme;
  }, [theme, systemTheme]);

  // Synchronize 'dark' class on document.documentElement
  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (resolvedTheme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [resolvedTheme]);

  const setTheme = useCallback((newTheme: ThemeMode) => {
    setThemeState(newTheme);
    if (typeof window !== "undefined" && window.localStorage) {
      try {
        window.localStorage.setItem(STORAGE_KEY, newTheme);
      } catch {
        // Ignore localStorage quota/permission errors
      }
    }
  }, []);

  const toggleTheme = useCallback(() => {
    const next: ThemeMode = resolvedTheme === "dark" ? "light" : "dark";
    setTheme(next);
  }, [resolvedTheme, setTheme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
      toggleTheme,
    }),
    [theme, resolvedTheme, setTheme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): ThemeContextValue => {
  const context = useContext(ThemeContext);
  if (!context) {
    const systemFallback = getSystemTheme();
    return {
      theme: "system",
      resolvedTheme: systemFallback,
      setTheme: () => {},
      toggleTheme: () => {},
    };
  }
  return context;
};
