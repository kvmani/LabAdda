import { Dialog } from "../../ui";
import "./shortcuts.css";

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function ShortcutsModal({ isOpen, onClose }: Props) {
  return (
    <Dialog open={isOpen} title="Keyboard Shortcuts" onClose={onClose}>
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
    </Dialog>
  );
}
