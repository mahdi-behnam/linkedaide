import React from "react";
import { Sparkle, ShieldCheck } from "../icons";

interface PillarBenchmarkCardProps {
  topicPillar: string;
}

export const PillarBenchmarkCard: React.FC<PillarBenchmarkCardProps> = ({
  topicPillar,
}) => {
  const guidelines = React.useMemo(() => {
    const p = (topicPillar || "").toLowerCase();
    if (p.includes("system") || p.includes("distrib") || p.includes("infra")) {
      return {
        focus: "Architecture & Resilience",
        hook: "Contrast naive implementation with fault-tolerant patterns.",
        length: "150 - 250 words with structural bullet points.",
        tip: "Highlight state reconciliation and failure modes.",
      };
    }
    if (p.includes("ai") || p.includes("llm") || p.includes("agent")) {
      return {
        focus: "Enterprise AI & Determinism",
        hook: "Focus on human-in-the-loop verification over raw autonomy.",
        length: "120 - 200 words with concrete architectural lessons.",
        tip: "Avoid marketing hyperbole; emphasize reliability invariants.",
      };
    }
    if (p.includes("browser") || p.includes("playwright") || p.includes("scrap")) {
      return {
        focus: "Automation Engineering",
        hook: "Discuss selector drift resilience and bot-challenge handling.",
        length: "100 - 180 words with specific technical takeaways.",
        tip: "Emphasize anti-entropy and idempotent execution.",
      };
    }
    return {
      focus: "Thought Leadership",
      hook: "Open with a sharp, contrarian industry observation.",
      length: "120 - 220 words optimized for the LinkedIn mobile cutoff.",
      tip: "Invite technical debate with an open question.",
    };
  }, [topicPillar]);

  return (
    <div className="p-4 rounded-lg bg-surface-container-lowest border border-outline/70 shadow-2xs flex flex-col gap-2.5">
      <div className="flex items-center justify-between pb-1 border-b border-outline/50">
        <div className="flex items-center gap-2">
          <Sparkle size={16} className="text-secondary" />
          <span className="text-xs font-semibold text-on-surface">
            Pillar Editorial Strategy
          </span>
        </div>
        <span className="text-[11px] text-tertiary font-medium">
          {guidelines.focus}
        </span>
      </div>

      <p className="text-xs text-on-surface-variant leading-relaxed">
        Editorial guidelines for <strong className="text-on-surface font-medium">{topicPillar}</strong> to maximize signal and engagement quality.
      </p>

      <div className="pt-2 border-t border-outline/50 flex flex-col gap-2 text-xs">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant">Recommended Hook</span>
          <span className="text-on-surface text-[11px]">{guidelines.hook}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant">Recommended Length</span>
          <span className="text-on-surface font-mono text-[11px]">{guidelines.length}</span>
        </div>
        <div className="flex items-center gap-1.5 pt-1 text-on-surface-variant text-[11px] border-t border-outline/30">
          <ShieldCheck size={13} className="text-primary shrink-0" />
          <span className="text-[10px] leading-tight">{guidelines.tip}</span>
        </div>
      </div>
    </div>
  );
};
