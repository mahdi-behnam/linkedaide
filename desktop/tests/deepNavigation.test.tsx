import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React from "react";
import { AppProvider, useApp } from "../src/context/AppContext";
import { useDeepNavigation, highlightAndScrollTo } from "../src/hooks/useDeepNavigation";

describe("Deep Navigation Framework & DOM Highlight", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("finds elements and applies temporary ring highlight classes", () => {
    const div = document.createElement("div");
    div.id = "target-card";
    div.scrollIntoView = vi.fn();
    document.body.appendChild(div);

    const found = highlightAndScrollTo("target-card", { durationMs: 1000 });
    expect(found).toBe(true);
    expect(div.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    expect(div.classList.contains("ring-2")).toBe(true);
    expect(div.classList.contains("ring-primary")).toBe(true);

    // Fast-forward timer to verify cleanup
    act(() => {
      vi.advanceTimersByTime(1050);
    });

    expect(div.classList.contains("ring-2")).toBe(false);
    document.body.removeChild(div);
  });

  it("returns false gracefully if target element is not found", () => {
    const found = highlightAndScrollTo("non-existent-card");
    expect(found).toBe(false);
  });

  it("dispatches navigation target through AppContext and triggers useDeepNavigation", () => {
    const targetHandlerMock = vi.fn();

    const TestComponent = () => {
      const { navigateTo } = useApp();
      useDeepNavigation("settings", targetHandlerMock);

      return (
        <div>
          <button
            data-testid="trigger-nav"
            onClick={() =>
              navigateTo({
                tab: "settings",
                sectionId: "setting-nim-intelligence",
              })
            }
          >
            Navigate To NIM
          </button>
        </div>
      );
    };

    render(
      <AppProvider>
        <TestComponent />
      </AppProvider>
    );

    expect(targetHandlerMock).not.toHaveBeenCalled();

    const btn = screen.getByTestId("trigger-nav");
    act(() => {
      btn.click();
    });

    expect(targetHandlerMock).toHaveBeenCalledTimes(1);
    expect(targetHandlerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        tab: "settings",
        sectionId: "setting-nim-intelligence",
      })
    );
  });
});
