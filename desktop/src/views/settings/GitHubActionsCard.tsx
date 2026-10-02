import React from "react";
import { Lightning, Eye } from "../../components/icons";

interface GitHubActionsCardProps {
  executionMode: "cloud" | "local";
  githubRepoOwner: string;
  githubRepoName: string;
  githubDispatchPat: string;
  showGithubPat: boolean;
  onToggleShowPat: () => void;
  onRepoOwnerChange: (owner: string) => void;
  onRepoNameChange: (name: string) => void;
  onDispatchPatChange: (pat: string) => void;
}

export const GitHubActionsCard: React.FC<GitHubActionsCardProps> = ({
  executionMode,
  githubRepoOwner,
  githubRepoName,
  githubDispatchPat,
  showGithubPat,
  onToggleShowPat,
  onRepoOwnerChange,
  onRepoNameChange,
  onDispatchPatChange,
}) => {
  return (
    <div className="flex flex-col gap-4 p-6 rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500 shrink-0">
            <Lightning size={18} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface">
              GitHub Actions Cloud Runner Dispatch
            </h2>
            <p className="font-label-sm text-label-sm text-on-surface-variant">
              Workflow dispatch triggers for scout.yml and execute.yml
            </p>
          </div>
        </div>

        {executionMode === "cloud" && (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-0.5 text-[11px] font-mono text-amber-500 font-semibold self-start sm:self-auto">
            Required for Cloud Mode
          </span>
        )}
      </div>

      <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
        Dispatches automated workflows (<code className="font-code-sm text-code-sm text-on-surface px-1 py-0.5 rounded bg-surface-container">scout.yml</code> and <code className="font-code-sm text-code-sm text-on-surface px-1 py-0.5 rounded bg-surface-container">execute.yml</code>) via GitHub Actions when using Cloud Remote Runner. Configure your repository coordinates and a Personal Access Token (PAT).
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-1">
        {/* Repo Owner */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            GitHub Repository Owner
          </label>
          <input
            type="text"
            value={githubRepoOwner}
            onChange={(e) => onRepoOwnerChange(e.target.value)}
            placeholder="e.g. mahdi-behnam"
            className="w-full px-3.5 py-2.5 rounded-xl bg-surface-container-low focus:bg-surface-container-lowest border border-surface-container-high focus:border-amber-500 outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant"
          />
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Username or organization owning the repository
          </span>
        </div>

        {/* Repo Name */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            GitHub Repository Name
          </label>
          <input
            type="text"
            value={githubRepoName}
            onChange={(e) => onRepoNameChange(e.target.value)}
            placeholder="e.g. linkedin-hitl-agent"
            className="w-full px-3.5 py-2.5 rounded-xl bg-surface-container-low focus:bg-surface-container-lowest border border-surface-container-high focus:border-amber-500 outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant"
          />
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Repository name hosting the agent workflows
          </span>
        </div>
      </div>

      {/* GitHub PAT */}
      <div className="flex flex-col gap-1.5 pt-1">
        <div className="flex items-center justify-between">
          <label className="font-body-strong text-body-strong text-on-surface">
            GitHub Personal Access Token (GITHUB_DISPATCH_PAT)
          </label>
          <button
            type="button"
            aria-label="Toggle GitHub PAT visibility"
            onClick={onToggleShowPat}
            className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
          >
            <Eye size={14} />
            <span>{showGithubPat ? "Hide" : "Show"}</span>
          </button>
        </div>

        <input
          type={showGithubPat ? "text" : "password"}
          value={githubDispatchPat}
          onChange={(e) => onDispatchPatChange(e.target.value)}
          placeholder="Enter GITHUB_DISPATCH_PAT (ghp_... or github_pat_...)"
          className="w-full px-3.5 py-2.5 rounded-xl bg-surface-container-low focus:bg-surface-container-lowest border border-surface-container-high focus:border-amber-500 outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant"
        />

        <div className="mt-1 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3 text-xs space-y-1.5 text-on-surface-variant">
          <span className="font-semibold text-amber-500">
            Required GitHub Personal Access Token (PAT) Scopes:
          </span>
          <ul className="list-disc list-inside space-y-1">
            <li>
              <strong className="text-on-surface">Classic PAT (<code className="font-mono">ghp_...</code>):</strong> Must check both <code className="text-amber-500 font-mono font-semibold">workflow</code> (&quot;Update GitHub Action workflows&quot;) AND <code className="text-amber-500 font-mono font-semibold">repo</code>.
            </li>
            <li>
              <strong className="text-on-surface">Fine-grained PAT (<code className="font-mono">github_pat_...</code>):</strong> Under <em>Repository Permissions</em>, set <code className="text-amber-500 font-mono font-semibold">Actions</code> to <strong>Read and write</strong>.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
