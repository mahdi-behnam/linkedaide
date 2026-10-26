/**
 * LLM service helper for Cloudflare Worker.
 *
 * Provides tone rewrite and draft regeneration using NVIDIA NIM Chat Completions API.
 */

import { Env } from "../types";

export const VALID_TONES = [
  "technical",
  "inquisitive",
  "contrarian",
  "shorter",
  "regenerate",
  "casual",
  "concise",
] as const;

export type ValidTone = (typeof VALID_TONES)[number];

export const TONE_INSTRUCTIONS: Record<string, string> = {
  technical:
    "Rewrite with technical depth, precise industry terminology, analytical rigor, and concrete domain substance.",
  inquisitive:
    "Rewrite with an inquisitive angle, asking an engaging, open-ended question that prompts meaningful industry discussion.",
  contrarian:
    "Rewrite with a constructive contrarian perspective, politely challenging common industry assumptions with clear rationale.",
  shorter:
    "Rewrite to be concise, punchy, and direct, removing filler words while keeping the core insight.",
  regenerate:
    "Provide an alternative fresh draft with engaging domain insights, sharp perspective, and natural conversational flow.",
  casual:
    "Rewrite in a warm, approachable, conversational tone suitable for direct professional outreach.",
  concise:
    "Rewrite to be brief, clear, and high-impact within 300 characters.",
};

export async function rewriteDraftWithLlm(
  env: Env,
  draftText: string,
  tone: string,
  postExcerpt?: string
): Promise<string> {
  if (!env.NVIDIA_NIM_API_KEY) {
    throw new Error("NVIDIA_NIM_API_KEY is not configured");
  }

  const baseUrl = (env.LLM_BASE_URL || "https://integrate.api.nvidia.com/v1").replace(/\/+$/, "");
  const llmUrl = `${baseUrl}/chat/completions`;

  const toneModifier = TONE_INSTRUCTIONS[tone] || `Rewrite in a ${tone} tone.`;
  const systemPrompt =
    "You are an expert LinkedIn ghostwriter and editor. Your task is to rewrite a draft comment according to the specified tone instruction while preserving authenticity and professional voice. Return ONLY the rewritten text without greetings, explanations, or quotes.";

  const userPrompt = postExcerpt
    ? `Context Post:\n"${postExcerpt}"\n\nOriginal Draft:\n"${draftText}"\n\nTone Instruction:\n${toneModifier}\n\nRewritten Draft:`
    : `Original Draft:\n"${draftText}"\n\nTone Instruction:\n${toneModifier}\n\nRewritten Draft:`;

  const modelName =
    env.NIM_MODEL_PRIMARY || env.LLM_MODEL || "meta/llama-3.3-70b-instruct";

  const llmResp = await fetch(llmUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${env.NVIDIA_NIM_API_KEY}`,
    },
    body: JSON.stringify({
      model: modelName,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.6,
      max_tokens: 500,
    }),
  });

  if (!llmResp.ok) {
    const errText = await llmResp.text();
    throw new Error(`LLM API returned ${llmResp.status}: ${errText}`);
  }

  const completionData = (await llmResp.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };

  const rewritten = completionData.choices?.[0]?.message?.content?.trim();
  if (!rewritten) {
    throw new Error("Empty completion returned from LLM provider");
  }

  return rewritten;
}
