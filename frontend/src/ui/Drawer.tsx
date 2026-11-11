import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "./focus";
import { IconButton } from "./IconButton";
import "./overlay.css";

type DrawerProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
};

/** A detail panel from the right edge; the list behind it keeps its place and filters (UX-03). */
export function Drawer({ open, title, onClose, children, footer }: DrawerProps) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(panel, open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="ui-overlay ui-overlay--drawer">
      <div
        className="ui-overlay__backdrop ui-overlay__backdrop--light"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        ref={panel}
        className="ui-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="ui-dialog__header">
          <h2 className="ui-dialog__title" id={titleId}>
            {title}
          </h2>
          <IconButton icon="close" label="Close panel" onClick={onClose} />
        </header>
        <div className="ui-drawer__body">{children}</div>
        {footer && <footer className="ui-dialog__footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
