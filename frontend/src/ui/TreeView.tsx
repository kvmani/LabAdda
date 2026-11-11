import { useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Icon } from "./Icon";
import "./navigation.css";

export type TreeNode = {
  id: string;
  label: string;
  /** Extra text after the label, such as a count. Read after the label. */
  detail?: ReactNode;
  children?: TreeNode[];
};

type VisibleItem = {
  node: TreeNode;
  level: number;
  parentId: string | null;
  position: number;
  setSize: number;
};

/** The nodes a user can currently see, in display order. */
export function visibleItems(nodes: TreeNode[], expanded: Set<string>): VisibleItem[] {
  const items: VisibleItem[] = [];
  function walk(list: TreeNode[], level: number, parentId: string | null) {
    list.forEach((node, index) => {
      items.push({ node, level, parentId, position: index + 1, setSize: list.length });
      if (node.children?.length && expanded.has(node.id)) walk(node.children, level + 1, node.id);
    });
  }
  walk(nodes, 1, null);
  return items;
}

type TreeViewProps = {
  label: string;
  nodes: TreeNode[];
  selectedId?: string | null;
  onSelect: (node: TreeNode) => void;
  /** Nodes open at first; usually the path to the selected node. */
  initiallyExpanded?: string[];
};

/**
 * A keyboard-operable tree (WAI-ARIA tree view): Up and Down move, Right opens or goes to the
 * first child, Left closes or goes to the parent, Home and End jump, Enter or Space selects.
 */
export function TreeView({
  label,
  nodes,
  selectedId = null,
  onSelect,
  initiallyExpanded = [],
}: TreeViewProps) {
  const [expanded, setExpanded] = useState(() => new Set(initiallyExpanded));
  const items = useMemo(() => visibleItems(nodes, expanded), [nodes, expanded]);
  const [focusedId, setFocusedId] = useState<string | null>(selectedId ?? nodes[0]?.id ?? null);
  const tree = useRef<HTMLUListElement>(null);
  const tabStop = items.some((item) => item.node.id === focusedId) ? focusedId : (items[0]?.node.id ?? null);

  function focus(id: string | null | undefined) {
    if (!id) return;
    setFocusedId(id);
    const elements = tree.current?.querySelectorAll<HTMLElement>("[data-node]") ?? [];
    Array.from(elements)
      .find((element) => element.dataset.node === id)
      ?.focus();
  }

  function setOpen(id: string, open: boolean) {
    setExpanded((current) => {
      const next = new Set(current);
      if (open) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function onKeyDown(event: KeyboardEvent, index: number) {
    const item = items[index];
    if (!item) return;
    const { node, parentId } = item;
    const hasChildren = Boolean(node.children?.length);
    const isOpen = expanded.has(node.id);
    const handlers: Record<string, () => void> = {
      ArrowDown: () => focus(items[index + 1]?.node.id),
      ArrowUp: () => focus(items[index - 1]?.node.id),
      Home: () => focus(items[0]?.node.id),
      End: () => focus(items[items.length - 1]?.node.id),
      ArrowRight: () => {
        if (hasChildren && !isOpen) setOpen(node.id, true);
        else if (hasChildren) focus(node.children?.[0]?.id);
      },
      ArrowLeft: () => {
        if (hasChildren && isOpen) setOpen(node.id, false);
        else focus(parentId);
      },
      Enter: () => onSelect(node),
      " ": () => onSelect(node),
    };
    const handler = handlers[event.key];
    if (!handler) return;
    event.preventDefault();
    event.stopPropagation();
    handler();
  }

  return (
    <ul ref={tree} className="ui-tree" role="tree" aria-label={label}>
      {items.map((item, index) => {
        const { node, level, position, setSize } = item;
        const hasChildren = Boolean(node.children?.length);
        const isOpen = expanded.has(node.id);
        return (
          <li
            key={node.id}
            role="treeitem"
            data-node={node.id}
            aria-level={level}
            aria-posinset={position}
            aria-setsize={setSize}
            aria-expanded={hasChildren ? isOpen : undefined}
            aria-selected={node.id === selectedId}
            tabIndex={node.id === tabStop ? 0 : -1}
            className="ui-tree__item"
            onKeyDown={(event) => onKeyDown(event, index)}
            onFocus={() => setFocusedId(node.id)}
            onClick={() => {
              setFocusedId(node.id);
              onSelect(node);
            }}
          >
            <span
              className="ui-tree__toggle"
              aria-hidden="true"
              onClick={(event) => {
                if (!hasChildren) return;
                event.stopPropagation();
                setOpen(node.id, !isOpen);
              }}
            >
              {hasChildren && <Icon name={isOpen ? "chevron-down" : "chevron-right"} size="sm" />}
            </span>
            <span className="ui-tree__label">{node.label}</span>
            {node.detail !== undefined && <span className="ui-tree__detail">{node.detail}</span>}
          </li>
        );
      })}
    </ul>
  );
}
