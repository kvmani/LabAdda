import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import "./navigation.css";

export type TabItem = { id: string; label: string };

type TabsProps = {
  label: string;
  tabs: TabItem[];
  selected: string;
  /** Called when a tab is chosen. Pages usually navigate, so every tab has its own URL. */
  onSelect: (id: string) => void;
  /** Content of the selected tab. */
  children: ReactNode;
};

/** Tabs with roving focus: arrow keys, Home and End move between tabs and select them. */
export function Tabs({ label, tabs, selected, onSelect, children }: TabsProps) {
  const base = useId();
  const list = useRef<HTMLDivElement>(null);

  function focusTab(index: number) {
    const tab = tabs[(index + tabs.length) % tabs.length];
    if (!tab) return;
    onSelect(tab.id);
    list.current?.querySelector<HTMLElement>(`[data-tab="${tab.id}"]`)?.focus();
  }

  function onKeyDown(event: KeyboardEvent, index: number) {
    const targets: Record<string, number> = {
      ArrowRight: index + 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: tabs.length - 1,
    };
    const target = targets[event.key];
    if (target === undefined) return;
    event.preventDefault();
    focusTab(target);
  }

  return (
    <div className="ui-tabs">
      <div ref={list} className="ui-tabs__list" role="tablist" aria-label={label}>
        {tabs.map((tab, index) => {
          const isSelected = tab.id === selected;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${base}-tab-${tab.id}`}
              data-tab={tab.id}
              aria-selected={isSelected}
              aria-controls={`${base}-panel`}
              tabIndex={isSelected ? 0 : -1}
              className="ui-tabs__tab"
              onClick={() => onSelect(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        className="ui-tabs__panel"
        role="tabpanel"
        id={`${base}-panel`}
        aria-labelledby={`${base}-tab-${selected}`}
        tabIndex={0}
      >
        {children}
      </div>
    </div>
  );
}
