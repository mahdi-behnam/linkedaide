import { SearchDocument, ScoredSearchResult } from "./types";

/**
 * Tokenize a search query into non-empty, lowercase words.
 */
export function tokenizeQuery(query: string): string[] {
  return query
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0);
}

/**
 * Score a single document against normalized query terms.
 */
export function scoreDocument(
  doc: SearchDocument,
  query: string,
  tokens: string[]
): ScoredSearchResult | null {
  if (tokens.length === 0) {
    return {
      document: doc,
      score: 1,
      matchedTerms: [],
    };
  }

  const titleLower = doc.title.toLowerCase();
  const subtitleLower = doc.subtitle.toLowerCase();
  const categoryLower = doc.category.toLowerCase();
  const keywordsLower = doc.keywords.map((k) => k.toLowerCase());
  const queryLower = query.toLowerCase().trim();

  // Every token must match somewhere across title, subtitle, category, or keywords
  const matchedTerms: string[] = [];

  for (const token of tokens) {
    const inTitle = titleLower.includes(token);
    const inSubtitle = subtitleLower.includes(token);
    const inCategory = categoryLower.includes(token);
    const inKeywords = keywordsLower.some((k) => k.includes(token));

    if (inTitle || inSubtitle || inCategory || inKeywords) {
      matchedTerms.push(token);
    } else {
      // Must match all tokens for high-precision search
      return null;
    }
  }

  let score = 0;

  // Exact full title match
  if (titleLower === queryLower) {
    score += 150;
  } else if (titleLower.startsWith(queryLower)) {
    score += 90;
  }

  // Word-boundary matches in title
  const titleWords = titleLower.split(/\s+/);
  for (const token of tokens) {
    // Exact word match in title
    if (titleWords.includes(token)) {
      score += 40;
    } else if (titleWords.some((w) => w.startsWith(token))) {
      score += 30;
    } else if (titleLower.includes(token)) {
      score += 20;
    }

    // Subtitle matches
    if (subtitleLower.includes(token)) {
      score += 15;
    }

    // Keyword matches
    if (keywordsLower.some((k) => k === token)) {
      score += 25;
    } else if (keywordsLower.some((k) => k.startsWith(token))) {
      score += 15;
    }

    // Category match
    if (categoryLower.startsWith(token)) {
      score += 12;
    }
  }

  // Category priority boost for high-frequency actions and views
  if (doc.category === "Action") {
    score += 8;
  } else if (doc.category === "Navigation") {
    score += 5;
  } else if (doc.category === "Queue") {
    score += 6;
  } else if (doc.category === "Setting") {
    score += 4;
  }

  return {
    document: doc,
    score,
    matchedTerms,
  };
}

/**
 * Filter, score, and rank a collection of search documents against a user query.
 */
export function searchAndRank(
  documents: SearchDocument[],
  query: string,
  limit: number = 25
): SearchDocument[] {
  const trimmed = query.trim();
  const tokens = tokenizeQuery(trimmed);

  if (tokens.length === 0) {
    return documents.slice(0, limit);
  }

  const scoredResults: ScoredSearchResult[] = [];

  for (const doc of documents) {
    const result = scoreDocument(doc, trimmed, tokens);
    if (result && result.score > 0) {
      scoredResults.push(result);
    }
  }

  scoredResults.sort((a, b) => {
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    // Stable tie-breaker: title length (shorter title first) then alphabetic
    if (a.document.title.length !== b.document.title.length) {
      return a.document.title.length - b.document.title.length;
    }
    return a.document.title.localeCompare(b.document.title);
  });

  return scoredResults.slice(0, limit).map((r) => r.document);
}
