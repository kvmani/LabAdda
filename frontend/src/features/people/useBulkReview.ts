import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorCode, errorMessage, errorStatus, outcomeUnknown } from "../../api";
import { invalidate } from "../../generation";
import type { BulkItem, BulkReceipt, ChangePlan } from "./changeTypes";
import type { ReviewProblem } from "./useChangeReview";

type Phase = "checking" | "ready" | "saving" | "saved";

function describe(error: unknown): ReviewProblem {
  if (errorStatus(error) === 409)
    return { kind: "conflict", message: "Something changed since this review. Check the fresh plan below." };
  if (errorCode(error) === "offline") return { kind: "offline", message: errorMessage(error) };
  if (outcomeUnknown(error))
    return {
      kind: "unconfirmed",
      message: "The changes could not be confirmed. Reload the people list before trying again.",
    };
  return { kind: "error", message: errorMessage(error) };
}

/** Review many ordinary changes together, then apply exactly the reviewed plan (all or nothing). */
export function useBulkReview(requests: BulkItem[], onDenied: () => void) {
  const generation = useRef(0);
  const [phase, setPhase] = useState<Phase>("checking");
  const [plan, setPlan] = useState<ChangePlan | null>(null);
  const [problem, setProblem] = useState<ReviewProblem | null>(null);
  const [receipt, setReceipt] = useState<BulkReceipt | null>(null);
  useEffect(() => () => invalidate(generation), []);

  const fail = useCallback(
    (error: unknown, fallback: Phase) => {
      if ([401, 403].includes(errorStatus(error) ?? 0)) onDenied();
      setProblem(describe(error));
      setPhase(fallback);
    },
    [onDenied],
  );

  const preview = useCallback(async () => {
    const token = ++generation.current;
    setPhase("checking");
    setPlan(null);
    try {
      const result = await api<ChangePlan>("/admin/changes/bulk/preview", { body: { requests } });
      if (token !== generation.current) return;
      setPlan(result);
      setPhase("ready");
    } catch (error: unknown) {
      if (token === generation.current) fail(error, "ready");
    }
  }, [requests, fail]);

  useEffect(() => {
    void preview();
  }, [preview]);

  const confirm = useCallback(
    async (reason: string) => {
      if (!plan) return;
      const token = ++generation.current;
      setPhase("saving");
      setProblem(null);
      try {
        const body = { requests, digest: plan.digest, revisions: plan.revisions, reason };
        const result = await api<BulkReceipt>("/admin/changes/bulk/apply", { body });
        if (token !== generation.current) return;
        setReceipt(result);
        setPhase("saved");
      } catch (error: unknown) {
        if (token !== generation.current) return;
        fail(error, "ready");
        if (errorStatus(error) === 409) void preview();
      }
    },
    [plan, requests, fail, preview],
  );

  return { phase, plan, problem, receipt, confirm, retry: preview };
}
