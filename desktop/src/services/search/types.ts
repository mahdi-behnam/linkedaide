import React from "react";
import { NavigationTab } from "../../types";
import { IconProps } from "../../components/icons";

export type SearchCategory =
  | "Navigation"
  | "Queue"
  | "Outreach"
  | "Post"
  | "Schedule"
  | "History"
  | "Setting"
  | "Diagnostic"
  | "Action";

export interface NavigationTarget {
  tab: NavigationTab;
  itemId?: string;
  sectionId?: string;
  action?: string;
  targetField?: string;
  timestamp?: number;
}

export interface SearchDocument {
  id: string;
  title: string;
  subtitle: string;
  category: SearchCategory;
  icon: React.ComponentType<IconProps>;
  badge?: string;
  keywords: string[];
  target: NavigationTarget;
  action?: () => void;
  metadata?: Record<string, unknown>;
}

export interface ScoredSearchResult {
  document: SearchDocument;
  score: number;
  matchedTerms: string[];
}
