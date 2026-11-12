import { useEffect, useRef, useState } from "react";
import { invalidate } from "./generation";
import { realtime, type RealtimeEvent } from "./realtime";

const CHANGE_EVENTS = ["tasks.changed", "subscribed", "access_changed"];
const DENIAL_EVENTS = ["revoked", "subscribe_failed", "session_ended"];

/**
 * Tells a task screen that shared tasks may have changed, using content-free socket hints.
 * Hints never replace drafts. Only acknowledge the version that was fetched: a signal that
 * arrives during a request must stay pending after that request's response.
 */
export function useTaskUpdates(workspaceIds: string[], denied?: () => void) {
  const [pending, setPending] = useState(false);
  const version = useRef(0);
  const deniedRef = useRef(denied);
  deniedRef.current = denied;
  const scope = [...workspaceIds].sort().join("|");

  useEffect(() => {
    version.current += 1;
    setPending(false);
    let active = true;

    function markChanged() {
      version.current += 1;
      setPending(true);
    }

    function handleEvent(event: RealtimeEvent) {
      if (!active) return;
      if (CHANGE_EVENTS.includes(event.type)) markChanged();
      if (DENIAL_EVENTS.includes(event.type)) {
        markChanged();
        deniedRef.current?.();
      }
    }

    const watchedIds = scope ? scope.split("|") : [];
    const unsubscribers = watchedIds.map((id) => realtime.subscribe(id, handleEvent));
    return () => {
      active = false;
      invalidate(version);
      unsubscribers.forEach((stop) => stop());
    };
  }, [scope]);

  return {
    pending,
    snapshot: () => version.current,
    acknowledge: (seenVersion: number) => {
      if (seenVersion === version.current) setPending(false);
    },
  };
}
