import React from "react";
import { Lightning, Eye, ArrowSquareOut, WarningCircle, CheckCircle } from "../../components/icons";

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
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-amber-500/10 flex items-center justify-center text-amber-500 shrink-0">
            <Lightning size={16} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              GitHub Actions Cloud Runner Dispatch
            </h2>
            <p className="font-label-sm text-[11px] text-on-surface-variant">
              Workflow dispatch triggers for scout.yml and execute.yml
            </p>
          </div>
        </div>

        {executionMode === "cloud" && (
          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            {!githubRepoOwner || !githubDispatchPat ? (
              <span className="text-[11px] font-mono text-amber-500 font-medium flex items-center gap-1">
                <WarningCircle size={12} weight="bold" /> Setup Needed
              </span>
            ) : (
              <span className="text-[11px] font-mono text-emerald-500 font-medium flex items-center gap-1">
                <CheckCircle size={12} weight="bold" /> Configured
              </span>
            )}
          </div>
        )}
      </div>

      <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed text-[12px]">
        Dispatches automated workflows (
        <code className="font-code-sm text-code-sm text-on-surface px-1 py-0.5 rounded bg-surface-container">
          scout.yml
        </code>{" "}
        and{" "}
        <code className="font-code-sm text-code-sm text-on-surface px-1 py-0.5 rounded bg-surface-container">
          execute.yml
        </code>
        ) via GitHub Actions when using Cloud Remote Runner. Configure your
        repository coordinates and a Personal Access Token (PAT).
      </p>

      {/* New User Onboarding Callout */}
      <div className="flex items-start gap-2.5 p-2.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-xs text-blue-700 dark:text-blue-300">
        <ArrowSquareOut size={16} className="shrink-0 mt-0.5 text-blue-500" />
        <div className="flex-1">
          <span className="font-semibold">New user setup: </span>
          Each operator runs their own private cloud runner. First{" "}
          <a
            href="https://github.com/mahdi-behnam/linkedaide/fork"
            target="_blank"
            rel="noopener noreferrer"
            className="underline font-semibold hover:text-blue-600 dark:hover:text-blue-200"
          >
            fork the LinkedAide repository on GitHub
          </a>
          , then enter your GitHub username and forked repository name below.
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-0.5">
        {/* Repo Owner */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            GitHub Repository Owner
          </label>
          <input
            type="text"
            value={githubRepoOwner}
            onChange={(e) => onRepoOwnerChange(e.target.value)}
            placeholder="e.g. your-github-username"
            className="w-full px-3 py-1.5 rounded-md bg-surface-container-low focus:bg-surface-container-lowest border border-outline-variant/30 focus:border-amber-500 outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant text-[12px]"
          />
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Username or organization owning the repository
          </span>
        </div>

        {/* Repo Name */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            GitHub Repository Name
          </label>
          <input
            type="text"
            value={githubRepoName}
            onChange={(e) => onRepoNameChange(e.target.value)}
            placeholder="e.g. linkedaide"
            className="w-full px-3 py-1.5 rounded-md bg-surface-container-low focus:bg-surface-container-lowest border border-outline-variant/30 focus:border-amber-500 outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant text-[12px]"
          />
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Repository name hosting the agent workflows
          </span>
        </div>
      </div>

      {/* GitHub PAT */}
      <div className="flex flex-col gap-1.5 pt-0.5">
        <div className="flex items-center justify-between">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            GitHub Personal Access Token (GITHUB_DISPATCH_PAT)
          </label>
          <button
            type="button"
            aria-label="Toggle GitHub PAT visibility"
            onClick={onToggleShowPat}
            className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
          >
            <Eye size={13} />
            <span>{showGithubPat ? "Hide" : "Show"}</span>
          </button>
        </div>

        <input
          type={showGithubPat ? "text" : "password"}
          value={githubDispatchPat}
          onChange={(e) => onDispatchPatChange(e.target.value)}
          placeholder="Enter GITHUB_DISPATCH_PAT (ghp_... or github_pat_...)"
          className="w-full px-3 py-1.5 rounded-md bg-surface-container-low focus:bg-surface-container-lowest border border-outline-variant/30 focus:border-amber-500 outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant text-[12px]"
        />

        <div className="mt-1 rounded-md border border-amber-500/25 bg-amber-500/5 p-2.5 text-xs space-y-1 text-on-surface-variant">
          <span className="font-semibold text-amber-500">
            Required GitHub Personal Access Token (PAT) Scopes:
          </span>
          <ul className="list-disc list-inside space-y-0.5">
            <li>
              <strong className="text-on-surface">
                Classic PAT (<code className="font-mono">ghp_...</code>):
              </strong>{" "}
              Must check both{" "}
              <code className="text-amber-500 font-mono font-semibold">
                workflow
              </code>{" "}
              (&quot;Update GitHub Action workflows&quot;) AND{" "}
              <code className="text-amber-500 font-mono font-semibold">
                repo
              </code>
              .
            </li>
            <li>
              <strong className="text-on-surface">
                Fine-grained PAT (
                <code className="font-mono">github_pat_...</code>):
              </strong>{" "}
              Under <em>Repository Permissions</em>, set{" "}
              <code className="text-amber-500 font-mono font-semibold">
                Actions
              </code>{" "}
              to <strong>Read and write</strong>.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
