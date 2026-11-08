import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { UploadQueue, type UploadedAsset } from "../uploads";

export function useUploadQueue(maxBytes: number, onComplete: (asset: UploadedAsset) => void) {
  const callback = useRef(onComplete);
  callback.current = onComplete;
  const [queue] = useState(() => new UploadQueue(maxBytes, asset => callback.current(asset)));
  const attempts = useSyncExternalStore(queue.subscribe, queue.snapshot);
  useEffect(() => { queue.open(); return () => queue.close(); }, [queue]);
  return {queue, attempts};
}

export function UploadRecovery({queue}: {queue: UploadQueue}) {
  const attempts = useSyncExternalStore(queue.subscribe, queue.snapshot);
  if (!attempts.length) return null;
  return <div className="notice" aria-label="Unresolved uploads">
    <p>Keep this view open until uploads are resolved. File contents and retry controls stay in memory only.</p>
    <ul className="plain">{attempts.map(a => <li key={a.key}>
      <strong>{a.file.name}</strong> <span role="status">{a.message}</span>
      {!a.busy && <span className="row wrap">
        <button type="button" className="ghost small" onClick={() => void queue.check(a.key)}>Check upload result</button>
        {a.retryable && <button type="button" className="ghost small" onClick={() => void queue.send(a.key)}>Retry same file</button>}
        <button type="button" className="ghost small" onClick={() => queue.dismiss(a.key)}>Dismiss upload</button>
      </span>}
    </li>)}</ul>
    <p className="muted small">Dismissing does not delete a stored file. Check My storage usage before choosing another copy.</p>
  </div>;
}
