import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Button } from "../ui";
import { UploadQueue, type UploadedAsset } from "../uploads";
import "./upload-recovery.css";

export function useUploadQueue(maxBytes: number, onComplete: (asset: UploadedAsset) => void) {
  const callback = useRef(onComplete);
  callback.current = onComplete;
  const [queue] = useState(() => new UploadQueue(maxBytes, (asset) => callback.current(asset)));
  const attempts = useSyncExternalStore(queue.subscribe, queue.snapshot);
  useEffect(() => {
    queue.open();
    return () => queue.close();
  }, [queue]);
  return { queue, attempts };
}

export function UploadRecovery({ queue }: { queue: UploadQueue }) {
  const attempts = useSyncExternalStore(queue.subscribe, queue.snapshot);
  if (!attempts.length) return null;
  return (
    <div className="upload-recovery" aria-label="Unresolved uploads">
      <p>
        Keep this view open until uploads are resolved. File contents and retry controls stay in memory only.
      </p>
      <ul>
        {attempts.map((a) => (
          <li key={a.key}>
            <strong>{a.file.name}</strong> <span role="status">{a.message}</span>
            {!a.busy && (
              <span className="upload-recovery__actions">
                <Button variant="quiet" size="sm" onClick={() => void queue.check(a.key)}>
                  Check upload result
                </Button>
                {a.retryable && (
                  <Button variant="quiet" size="sm" onClick={() => void queue.send(a.key)}>
                    Retry same file
                  </Button>
                )}
                <Button variant="quiet" size="sm" onClick={() => queue.dismiss(a.key)}>
                  Dismiss upload
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="upload-recovery__note">
        Dismissing does not delete a stored file. Check My storage usage before choosing another copy.
      </p>
    </div>
  );
}
