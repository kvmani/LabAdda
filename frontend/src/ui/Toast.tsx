import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icon";
import { IconButton } from "./IconButton";
import "./overlay.css";

type Toast = { id: number; message: string };
type ShowToast = (message: string) => void;

const ToastContext = createContext<ShowToast | null>(null);

/** How long a confirmation stays before it disappears on its own. */
export const TOAST_MILLISECONDS = 6000;

/**
 * Brief, non-blocking confirmations after a save has been committed (UX-02). Errors are shown
 * inline where they happened, never only in a toast.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback<ShowToast>(
    (message) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-2), { id, message }]);
      timers.current.set(
        id,
        window.setTimeout(() => dismiss(id), TOAST_MILLISECONDS),
      );
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((timer) => window.clearTimeout(timer));
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="ui-toasts" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className="ui-toast">
            <Icon name="success" />
            <span className="ui-toast__message">{toast.message}</span>
            <IconButton icon="close" label="Dismiss message" size="sm" onClick={() => dismiss(toast.id)} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/** Returns a function that shows a confirmation, for example `toast("Note saved.")`. */
export function useToast(): ShowToast {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside ToastProvider");
  return show;
}
