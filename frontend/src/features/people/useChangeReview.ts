import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorCode, errorMessage, errorStatus, outcomeUnknown } from "../../api";
import { invalidate } from "../../generation";
import type { ChangePlan, ChangeReceipt, ChangeRequest } from "./changeTypes";

export type ReviewProblem = { kind: "conflict" | "offline" | "unconfirmed" | "error"; message: string };
type Phase = "idle" | "checking" | "ready" | "saving" | "saved";

/** Explain a failed preview or apply in plain words; the draft request is always kept. */
function describe(error: unknown): ReviewProblem {
  if (errorStatus(error) === 409)
    return {
      kind: "conflict",
      message: "Someone changed this record or its consequences. Review the fresh plan before applying.",
    };
  if (errorCode(error) === "offline") return { kind: "offline", message: errorMessage(error) };
  if (outcomeUnknown(error))
    return {
      kind: "unconfirmed",
      message: "The change could not be confirmed. Reload the person's record before trying again.",
    };
  return { kind: "error", message: errorMessage(error) };
}

/** Preview, then apply exactly the reviewed plan; stale responses are dropped (generation counter). */
export function useChangeReview(onDenied: () => void) {
  const generation = useRef(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [plan, setPlan] = useState<ChangePlan | null>(null);
  const [problem, setProblem] = useState<ReviewProblem | null>(null);
  const [receipt, setReceipt] = useState<ChangeReceipt | null>(null);
  useEffect(() => () => invalidate(generation), []);

  const fail = useCallback(
    (error: unknown, fallback: Phase) => {
      if ([401, 403].includes(errorStatus(error) ?? 0)) onDenied();
      setProblem(describe(error));
      setPhase(fallback);
    },
    [onDenied],
  );

  const preview = useCallback(
    async (request: ChangeRequest, effectiveOn?: string) => {
      const token = ++generation.current;
      setPhase("checking");
      setPlan(null);
      try {
        const result = await api<ChangePlan>("/admin/changes/preview", {
          body: { request, effective_on: effectiveOn },
        });
        if (token !== generation.current) return;
        setPlan(result);
        setPhase("ready");
      } catch (error: unknown) {
        if (token === generation.current) fail(error, "idle");
      }
    },
    [fail],
  );

  const confirm = useCallback(
    async (request: ChangeRequest, reason: string, effectiveOn?: string) => {
      if (!plan) return;
      const token = ++generation.current;
      setPhase("saving");
      setProblem(null);
      try {
        const body = {
          request,
          digest: plan.digest,
          revisions: plan.revisions,
          reason,
          effective_on: effectiveOn,
        };
        const result = await api<ChangeReceipt>("/admin/changes/apply", { body });
        if (token !== generation.current) return;
        setReceipt(result);
        setPhase("saved");
      } catch (error: unknown) {
        if (token !== generation.current) return;
        fail(error, "ready");
        if (errorStatus(error) === 409) void preview(request, effectiveOn);
      }
    },
    [plan, fail, preview],
  );

  const reset = useCallback(() => {
    invalidate(generation);
    setPlan(null);
    setProblem(null);
    setPhase("idle");
  }, []);

  return { phase, plan, problem, receipt, preview, confirm, reset, clearProblem: () => setProblem(null) };
}
