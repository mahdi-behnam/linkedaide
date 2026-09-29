import { SlidersHorizontal, Globe } from "../components/icons";
import { useApp } from "../context/AppContext";

export const SettingsView: React.FC = () => {
  const { telemetry, quota } = useApp();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
            Agent Configuration & Settings
          </h1>
          <p className="mt-1 text-xs text-zinc-400">
            Runtime rate limits, Cloudflare KV edge connection, and NVIDIA NIM model preferences.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Worker & State Store */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-3">
            <Globe size={16} className="text-emerald-400" />
            <h3 className="text-xs font-semibold text-zinc-200">
              Cloudflare Workers Relay
            </h3>
          </div>
          <div className="mt-3 space-y-3 font-mono text-xs">
            <div>
              <span className="text-zinc-500">Worker Relay Endpoint:</span>
              <p className="mt-1 rounded border border-zinc-800 bg-zinc-950 p-2 text-zinc-300">
                {telemetry.workerUrl}
              </p>
            </div>
            <div>
              <span className="text-zinc-500">State Persistence Backend:</span>
              <p className="mt-1 rounded border border-zinc-800 bg-zinc-950 p-2 text-zinc-300">
                {telemetry.kvBackend} (Namespace: hitl-state)
              </p>
            </div>
          </div>
        </div>

        {/* Daily Safety Limits */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-3">
            <SlidersHorizontal size={16} className="text-violet-400" />
            <h3 className="text-xs font-semibold text-zinc-200">
              Daily Safety Thresholds
            </h3>
          </div>
          <div className="mt-3 space-y-2 font-mono text-xs">
            <div className="flex justify-between border-b border-zinc-800/60 pb-2">
              <span className="text-zinc-500">Max Comments / Day:</span>
              <span className="text-zinc-200">{quota.commentsMax}</span>
            </div>
            <div className="flex justify-between border-b border-zinc-800/60 pb-2">
              <span className="text-zinc-500">Max Posts / Day:</span>
              <span className="text-zinc-200">{quota.postsMax}</span>
            </div>
            <div className="flex justify-between border-b border-zinc-800/60 pb-2">
              <span className="text-zinc-500">Max Suggestions / Day:</span>
              <span className="text-zinc-200">{quota.suggestionsMax}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Approval TTL:</span>
              <span className="text-zinc-200">24 Hours</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
