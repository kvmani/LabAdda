import { useId } from "react";

type Tab = { board_index: number; title: string };
type Props = {
  tabs: Tab[];
  selected: number;
  label: string;
  canWrite: boolean;
  maximum: number;
  onSelect: (index: number) => void;
  onRename: (index: number, title: string) => void;
  onAdd: () => void;
};

/** Tab controls contain only tabs; rename and add remain independent keyboard actions. */
export function BoardTabs({ tabs, selected, label, canWrite, maximum, onSelect, onRename, onAdd }: Props) {
  const id = useId();
  const current = tabs.find((tab) => tab.board_index === selected);
  return (
    <div className="whiteboard-tabs">
      <div role="tablist" aria-label={label} className="whiteboard-tabs__list">
        {tabs.map((tab, position) => (
          <button
            key={tab.board_index}
            id={`${id}-${tab.board_index}`}
            type="button"
            role="tab"
            tabIndex={selected === tab.board_index ? 0 : -1}
            aria-selected={selected === tab.board_index}
            className={`whiteboard-tab ${selected === tab.board_index ? "whiteboard-tab--active" : ""}`}
            onClick={() => onSelect(tab.board_index)}
            onKeyDown={(event) => {
              const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
              if (!delta && event.key !== "Home" && event.key !== "End") return;
              event.preventDefault();
              const next =
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? tabs.length - 1
                    : (position + delta + tabs.length) % tabs.length;
              const target = tabs[next];
              if (!target) return;
              onSelect(target.board_index);
              document.getElementById(`${id}-${target.board_index}`)?.focus();
            }}
          >
            {tab.title}
          </button>
        ))}
      </div>
      {canWrite && current && (
        <button
          type="button"
          className="whiteboard-tab__add"
          onClick={() => onRename(current.board_index, current.title)}
        >
          Rename board
        </button>
      )}
      {canWrite && tabs.length < maximum && (
        <button
          type="button"
          className="whiteboard-tab__add"
          onClick={onAdd}
          title="Add a new whiteboard tab"
        >
          ＋ Add Board
        </button>
      )}
    </div>
  );
}
