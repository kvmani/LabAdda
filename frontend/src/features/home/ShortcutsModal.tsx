import { useEffect, useRef } from "react";
import "./shortcuts.css";

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function ShortcutsModal({ isOpen, onClose }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="shortcuts-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard Shortcuts"
      onClick={onClose}
    >
      <div
        className="shortcuts-card"
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        <div className="shortcuts-card__header">
          <div className="shortcuts-card__title-box">
            <span className="shortcuts-card__icon" aria-hidden="true">⌨️</span>
            <div>
              <h2 className="shortcuts-card__title">Keyboard Shortcuts</h2>
              <p className="shortcuts-card__subtitle">Fast navigation across your research workspace</p>
            </div>
          </div>
          <button
            type="button"
            className="shortcuts-card__close-btn"
            onClick={onClose}
            aria-label="Close shortcuts dialog"
          >
            ✕
          </button>
        </div>

        <div className="shortcuts-card__body">
          <div className="shortcuts-group">
            <h3 className="shortcuts-group__title">Quick Navigation</h3>
            <ul className="shortcuts-list">
              <li>
                <span className="shortcut-desc">Open My Whiteboard</span>
                <kbd className="shortcut-key">W</kbd>
              </li>
              <li>
                <span className="shortcut-desc">Open My Tasks</span>
                <kbd className="shortcut-key">T</kbd>
              </li>
              <li>
                <span className="shortcut-desc">Open Central Calendar</span>
                <kbd className="shortcut-key">C</kbd>
              </li>
              <li>
                <span className="shortcut-desc">Open My Notes</span>
                <kbd className="shortcut-key">O</kbd>
              </li>
            </ul>
          </div>

          <div className="shortcuts-group">
            <h3 className="shortcuts-group__title">Home Workbench Actions</h3>
            <ul className="shortcuts-list">
              <li>
                <span className="shortcut-desc">Focus Quick Note input</span>
                <kbd className="shortcut-key">N</kbd>
              </li>
              <li>
                <span className="shortcut-desc">Cycle Research Spark</span>
                <kbd className="shortcut-key">S</kbd>
              </li>
              <li>
                <span className="shortcut-desc">Show / Hide Shortcuts</span>
                <kbd className="shortcut-key">?</kbd>
              </li>
              <li>
                <span className="shortcut-desc">Close dialog / popup</span>
                <kbd className="shortcut-key">Esc</kbd>
              </li>
            </ul>
          </div>
        </div>

        <div className="shortcuts-card__footer">
          <p>
            💡 <strong>Pro-tip:</strong> Double-click anywhere on a whiteboard canvas to immediately place a sticky note!
          </p>
        </div>
      </div>
    </div>
  );
}
