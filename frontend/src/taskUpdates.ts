import { useEffect, useRef, useState } from "react";
import { realtime } from "./realtime";

/** Content-free hints never replace drafts. Only acknowledge the version fetched;
 * a signal arriving during a request must remain pending after its response.
 */
export function useTaskUpdates(workspaceIds: string[], denied?: () => void) {
  const [pending, setPending] = useState(false);
  const version = useRef(0),
    deniedRef = useRef(denied);
  deniedRef.current = denied;
  const scope = [...workspaceIds].sort().join("|");
  useEffect(() => {
    ++version.current;
    setPending(false);
    let active = true;
    const unsubscribe = (scope ? scope.split("|") : []).map((id) =>
      realtime.subscribe(id, (event) => {
        if (!active) return;
        if (["tasks.changed", "subscribed", "access_changed"].includes(event.type)) {
          ++version.current;
          setPending(true);
        }
        if (["revoked", "subscribe_failed", "session_ended"].includes(event.type)) {
          ++version.current;
          setPending(true);
          deniedRef.current?.();
        }
      }),
    );
    return () => {
      active = false;
      ++version.current;
      unsubscribe.forEach((stop) => stop());
    };
  }, [scope]);
  return {
    pending,
    snapshot: () => version.current,
    acknowledge: (seen: number) => {
      if (seen === version.current) setPending(false);
    },
  };
}
