import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ThemeProvider, useTheme } from "../src/context/ThemeContext";

const TestComponent: React.FC = () => {
  const { theme, resolvedTheme, setTheme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button data-testid="set-light" onClick={() => setTheme("light")}>
        Set Light
      </button>
      <button data-testid="set-dark" onClick={() => setTheme("dark")}>
        Set Dark
      </button>
      <button data-testid="set-system" onClick={() => setTheme("system")}>
        Set System
      </button>
      <button data-testid="toggle-theme" onClick={toggleTheme}>
        Toggle Theme
      </button>
    </div>
  );
};

describe("ThemeContext", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("defaults to system theme and adds dark class if system is dark", () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query === "(prefers-color-scheme: dark)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme").textContent).toBe("system");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("dynamically adds/removes dark class and persists override in localStorage", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    // Set to light
    fireEvent.click(screen.getByTestId("set-light"));
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("hitl_theme")).toBe("light");

    // Set to dark
    fireEvent.click(screen.getByTestId("set-dark"));
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("hitl_theme")).toBe("dark");

    // Toggle theme
    fireEvent.click(screen.getByTestId("toggle-theme"));
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("reads stored preference from localStorage on initialization", () => {
    localStorage.setItem("hitl_theme", "dark");

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
