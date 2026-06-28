import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig, PipelineStatus } from "../api";
import { HELP } from "../help";
import { InfoTip, LabelWithTip } from "./InfoTip";

interface Props {
  onComplete: () => void;
}

const STEP_ORDER = ["ingest", "extract", "llm", "save", "done"];

function stepState(
  stepId: string,
  current: string | null,
  pipelineState: PipelineStatus["state"],
  llmRan: boolean
): "pending" | "active" | "done" | "error" | "skipped" {
  if (stepId === "llm" && !llmRan && pipelineState !== "running") {
    return "skipped";
  }
  if (pipelineState === "error") {
    const idx = STEP_ORDER.indexOf(stepId);
    const curIdx = current ? STEP_ORDER.indexOf(current) : -1;
    if (idx < curIdx) return "done";
    if (idx === curIdx) return "error";
    return "pending";
  }
  if (pipelineState === "idle") return "pending";
  const idx = STEP_ORDER.indexOf(stepId);
  const curIdx = current ? STEP_ORDER.indexOf(current) : 0;
  if (pipelineState === "completed") {
    if (stepId === "llm" && !llmRan) return "skipped";
    return "done";
  }
  if (idx < curIdx) return "done";
  if (idx === curIdx) return "active";
  return "pending";
}

export function PipelinePanel({ onComplete }: Props) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [llmVerify, setLlmVerify] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    let wasRunning = false;
    const poll = async () => {
      try {
        const s = await api.pipelineStatus();
        if (!active) return;
        setStatus(s);
        if (wasRunning && s.state === "completed") onComplete();
        wasRunning = s.state === "running";
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 1500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [onComplete]);

  const running = status?.state === "running";

  const run = async (opts: { clear_cache?: boolean; use_cache?: boolean }) => {
    setError(null);
    try {
      const s = await api.pipelineRun({ ...opts, llm_verify: llmVerify });
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start pipeline");
    }
  };

  const dot = (s: ReturnType<typeof stepState>) => {
    const colors = {
      pending: "bg-slate-200 border-slate-300",
      active: "bg-blue-500 border-blue-600 animate-pulse",
      done: "bg-green-500 border-green-600",
      error: "bg-red-500 border-red-600",
      skipped: "bg-slate-100 border-slate-200",
    };
    return `w-3 h-3 rounded-full border-2 ${colors[s]}`;
  };

  const llmRan =
    status?.state === "running"
      ? status.step === "llm" || STEP_ORDER.indexOf(status.step ?? "") > STEP_ORDER.indexOf("llm")
      : Number(status?.result?.llm_calls ?? 0) > 0;

  return (
    <div className="bg-surface border border-border rounded-xl p-4 mb-6">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-800">Data Pipeline</h2>
          <p className="text-xs text-muted mt-0.5">
            Ingest from PCC → extract wounds → route → save
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-semibold px-2 py-1 rounded-full ${
              status?.state === "running"
                ? "bg-blue-100 text-blue-800"
                : status?.state === "completed"
                  ? "bg-green-100 text-green-800"
                  : status?.state === "error"
                    ? "bg-red-100 text-red-800"
                    : "bg-slate-100 text-slate-600"
            }`}
          >
            {status?.state ?? "idle"}
          </span>
          {config && (
            <span
              className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
                config.llm_available
                  ? "bg-violet-100 text-violet-800"
                  : config.llm_unavailable_reason === "missing_package"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-slate-100 text-muted"
              }`}
            >
              OpenAI{" "}
              {config.llm_available
                ? "ready"
                : config.llm_unavailable_reason === "missing_package"
                  ? "key set — install package"
                  : "not configured"}
              <InfoTip text={HELP.openai_badge} />
            </span>
          )}
        </div>
      </div>

      {/* Step visual */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
        {(status?.steps ?? [
          { id: "ingest", label: "Ingest" },
          { id: "extract", label: "Extract & route" },
          { id: "llm", label: "LLM suggestions" },
          { id: "save", label: "Save" },
        ]).map((step, i, arr) => (
          <div key={step.id} className="flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-1.5">
              <div className={dot(stepState(step.id, status?.step ?? null, status?.state ?? "idle", llmRan))} />
              <span className={`text-xs font-medium ${step.id === "llm" && !llmRan && status?.state === "completed" ? "text-slate-400" : "text-slate-700"}`}>
                {step.label}
                {step.id === "llm" && !llmRan && status?.state === "completed" ? " (skipped)" : ""}
              </span>
            </div>
            {i < arr.length - 1 && <div className="w-8 h-px bg-border" />}
          </div>
        ))}
      </div>

      {/* Progress bar */}
      {(running || status?.state === "completed") && (
        <div className="mb-3">
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-500"
              style={{ width: `${status?.progress ?? 0}%` }}
            />
          </div>
          <p className="text-xs text-muted mt-1">{status?.message}</p>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap gap-2 mb-3">
        <button
          type="button"
          disabled={running}
          onClick={() => run({ use_cache: true })}
          className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-md bg-slate-900 text-white font-medium disabled:opacity-40"
        >
          Run pipeline
          <InfoTip text={HELP.pipeline_run} className="text-white/80" />
        </button>
        <button
          type="button"
          disabled={running}
          onClick={() => run({ clear_cache: true, use_cache: true })}
          className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-md border border-border font-medium disabled:opacity-40"
        >
          Fresh fetch from API
          <InfoTip text={HELP.pipeline_fresh} />
        </button>
        <label className="flex items-center gap-1.5 text-sm ml-1">
          <input
            type="checkbox"
            checked={llmVerify}
            onChange={(e) => setLlmVerify(e.target.checked)}
            disabled={!config?.llm_available || running}
          />
          <LabelWithTip label="LLM suggest for review" tip={HELP.llm_verify} />
        </label>
      </div>

      {!config?.llm_available && (
        <p className="text-xs text-muted mb-2 bg-slate-50 border border-border rounded px-2 py-1.5">
          {config?.llm_unavailable_reason === "missing_package" ? (
            <>
              <strong>OpenAI:</strong> API key found, but the Python package is missing. Run{" "}
              <code className="text-[0.65rem]">pip install openai</code> in your venv, then restart{" "}
              <code className="text-[0.65rem]">python run_api.py</code>
            </>
          ) : (
            <>
              <strong>OpenAI:</strong> copy <code className="text-[0.65rem]">.env.example</code> to{" "}
              <code className="text-[0.65rem]">.env</code> and set{" "}
              <code className="text-[0.65rem]">OPENAI_API_KEY</code>, then restart{" "}
              <code className="text-[0.65rem]">python run_api.py</code>
            </>
          )}
        </p>
      )}

      {error && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1.5 mb-2">
          {error}
        </p>
      )}

      {/* Log tail */}
      {status && status.logs.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted font-medium">Pipeline log</summary>
          <pre className="mt-2 bg-slate-50 border border-border rounded p-2 max-h-32 overflow-y-auto text-[0.65rem] leading-relaxed">
            {status.logs.join("\n")}
          </pre>
        </details>
      )}

      {status?.result && status.state === "completed" && (
        <p className="text-xs text-green-700 mt-2">
          Last run: {String(status.result.elapsed_seconds)}s · {String(status.result.patients)} patients ·{" "}
          {String(status.result.auto_accept)} ready to bill · {String(status.result.rate_limited)} rate limits
          {status.result.llm_calls != null && Number(status.result.llm_calls) > 0 && (
            <> · {String(status.result.llm_calls)} LLM call(s), {String(status.result.llm_suggestions ?? 0)} suggestions</>
          )}
        </p>
      )}
    </div>
  );
}
