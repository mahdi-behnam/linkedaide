import { useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";
import { NavigationTab, NavigationTarget } from "../types";

export interface ScrollHighlightOptions {
  behavior?: ScrollBehavior;
  block?: ScrollLogicalPosition;
  durationMs?: number;
}

/**
 * Locate a target DOM element by ID, data-testid, or data-section, scroll it into view,
 * and apply a temporary glow highlight ring.
 */
export function highlightAndScrollTo(
  targetId: string,
  options?: ScrollHighlightOptions
): boolean {
  if (typeof document === "undefined") return false;

  const element =
    document.getElementById(targetId) ||
    document.querySelector(`[data-testid="${targetId}"]`) ||
    document.querySelector(`[data-section="${targetId}"]`) ||
    document.querySelector(`[id="${targetId}"]`);

  if (!element) return false;

  // Smoothly scroll into visible center
  element.scrollIntoView({
    behavior: options?.behavior || "smooth",
    block: options?.block || "center",
  });

  // Apply visual focus indicator
  const highlightClasses = [
    "ring-2",
    "ring-primary",
    "ring-offset-2",
    "ring-offset-surface",
    "shadow-lg",
    "transition-all",
    "duration-500",
  ];

  element.classList.add(...highlightClasses);

  const duration = options?.durationMs ?? 1800;
  setTimeout(() => {
    element.classList.remove(...highlightClasses);
  }, duration);

  return true;
}

/**
 * Hook for views to observe incoming deep navigation targets and trigger selection and scrolling.
 */
export function useDeepNavigation(
  tab: NavigationTab,
  onTarget?: (target: NavigationTarget) => void
) {
  const { currentTab, activeNavTarget, clearNavTarget } = useApp();
  const lastProcessedTimestampRef = useRef<number | null>(null);

  useEffect(() => {
    if (
      activeNavTarget &&
      currentTab === tab &&
      activeNavTarget.tab === tab &&
      activeNavTarget.timestamp !== lastProcessedTimestampRef.current
    ) {
      lastProcessedTimestampRef.current = activeNavTarget.timestamp ?? Date.now();

      // Notify view callback for state updates (e.g., selecting items)
      onTarget?.(activeNavTarget);

      // Attempt DOM scroll if target ID is designated
      const domTarget = activeNavTarget.sectionId || activeNavTarget.itemId;
      if (domTarget) {
        // Allow brief render cycle for tab content to mount / update
        const timer = setTimeout(() => {
          highlightAndScrollTo(domTarget);
        }, 120);
        return () => clearTimeout(timer);
      }
    }
  }, [currentTab, activeNavTarget, tab, onTarget, clearNavTarget]);
}
