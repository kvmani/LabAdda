import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "./focus";
import { IconButton } from "./IconButton";
import "./overlay.css";

type DialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** The action row, usually Cancel then the primary action. */
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
};

/** A modal dialog: focus stays inside until it closes, then returns to where it was (UX-02). */
export function Dialog({ open, title, onClose, children, footer, size = "md" }: DialogProps) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(panel, open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="ui-overlay">
      <div className="ui-overlay__backdrop" aria-hidden="true" onClick={onClose} />
      <div
        ref={panel}
        className={`ui-dialog ui-dialog--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="ui-dialog__header">
          <h2 className="ui-dialog__title" id={titleId}>
            {title}
          </h2>
          <IconButton icon="close" label="Close" onClick={onClose} />
        </header>
        <div className="ui-dialog__body">{children}</div>
        {footer && <footer className="ui-dialog__footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
