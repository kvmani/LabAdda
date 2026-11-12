import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Button, EmptyState } from "../../ui";
import { GAP_Y, NODE_HEIGHT, NODE_WIDTH, fitScale, layoutTree, type PlacedNode } from "./layout";
import type { OrgUnit } from "./types";
import type { DragPayload } from "./useDrag";

const PADDING = 16;
const STEP = 1.25;

function clip(text: string, length: number): string {
  return text.length > length ? text.slice(0, length - 1) + "…" : text;
}

function describe(unit: OrgUnit): string {
  const head = unit.head?.name ?? unit.acting_head?.name;
  const acting = !unit.head && unit.acting_head ? "Acting head " : "Head ";
  const parts = [`${unit.code ?? "No code"}, ${unit.name}`, head ? acting + head : "No head"];
  parts.push(`${unit.people} ${unit.people === 1 ? "person" : "people"}`);
  if (unit.archived) parts.push("closed");
  return parts.join(". ");
}

function Node({
  node,
  selected,
  focusable,
  collapsed,
  over,
  onSelect,
  onToggle,
  onKey,
  onDragStart,
  wasDrag,
}: {
  node: PlacedNode<OrgUnit>;
  selected: boolean;
  focusable: boolean;
  collapsed: boolean;
  over: boolean;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
  onKey: (event: KeyboardEvent, node: PlacedNode<OrgUnit>) => void;
  onDragStart: (event: React.PointerEvent, payload: DragPayload) => void;
  wasDrag: () => boolean;
}) {
  const { unit } = node;
  const head = unit.head?.name ?? (unit.acting_head ? `${unit.acting_head.name} (acting)` : "No head");
  const classes = ["org-node", selected && "org-node--selected", unit.archived && "org-node--closed"];
  if (over) classes.push("org-node--over");
  return (
    <g
      className={classes.filter(Boolean).join(" ")}
      transform={`translate(${node.x} ${node.y})`}
      role="treeitem"
      aria-selected={selected}
      aria-expanded={node.hasChildren ? !collapsed : undefined}
      aria-level={node.depth + 1}
      aria-label={describe(unit)}
      tabIndex={focusable ? 0 : -1}
      data-unit={unit.id}
      data-drop-unit={unit.id}
      onClick={() => !wasDrag() && onSelect(unit.id)}
      onKeyDown={(event) => onKey(event, node)}
      onPointerDown={(event) => onDragStart(event, { kind: "unit", id: unit.id, label: unit.name })}
    >
      <rect className="org-node__box" width={NODE_WIDTH} height={NODE_HEIGHT} rx={10} />
      <text className="org-node__code" x={12} y={20}>
        {clip(unit.code ?? "No code", 14)}
        {unit.archived ? " · Closed" : ""}
      </text>
      <text className="org-node__name" x={12} y={40}>
        {clip(unit.name, 25)}
      </text>
      <text className="org-node__line" x={12} y={58}>
        {clip(head, 28)}
      </text>
      <text className="org-node__line" x={12} y={74}>
        {unit.people} {unit.people === 1 ? "person" : "people"}
      </text>
      {node.hasChildren && (
        <g
          className="org-node__toggle"
          aria-hidden="true"
          transform={`translate(${NODE_WIDTH - 22} ${NODE_HEIGHT - 22})`}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            onToggle(unit.id);
          }}
        >
          <circle r={9} cx={9} cy={9} />
          <text x={9} y={13} textAnchor="middle">
            {collapsed ? "+" : "−"}
          </text>
        </g>
      )}
    </g>
  );
}

function connector(from: PlacedNode<OrgUnit>, to: PlacedNode<OrgUnit>): string {
  const x1 = from.x + NODE_WIDTH / 2;
  const x2 = to.x + NODE_WIDTH / 2;
  const middle = from.y + NODE_HEIGHT + GAP_Y / 2;
  return `M${x1} ${from.y + NODE_HEIGHT} V${middle} H${x2} V${to.y}`;
}

type Props = {
  units: OrgUnit[];
  selectedId: string | null;
  collapsed: ReadonlySet<string>;
  overId: string | null;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
  onCollapseAll: (collapse: boolean) => void;
  onDragStart: (event: React.PointerEvent, payload: DragPayload) => void;
  wasDrag: () => boolean;
};

/** The chart: tree layout drawn as SVG, with zoom, fit and a keyboard path through every unit. */
export function OrgChart({ units, selectedId, collapsed, overId, onSelect, onToggle, ...rest }: Props) {
  const layout = useMemo(() => layoutTree(units, collapsed), [units, collapsed]);
  const [zoom, setZoom] = useState(1);
  const [focusId, setFocusId] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const byId = useMemo(() => new Map(layout.nodes.map((node) => [node.unit.id, node])), [layout]);
  const focusable = byId.has(focusId ?? "")
    ? focusId
    : ((selectedId && byId.has(selectedId) ? selectedId : layout.nodes.find((n) => n.depth === 0)?.unit.id) ??
      null);

  useEffect(() => {
    const node = selectedId ? byId.get(selectedId) : undefined;
    const box = scroller.current;
    if (!node || !box || typeof box.scrollTo !== "function") return;
    box.scrollTo({
      left: Math.max(0, (node.x + PADDING) * zoom - box.clientWidth / 2 + (NODE_WIDTH * zoom) / 2),
      top: Math.max(0, (node.y + PADDING) * zoom - box.clientHeight / 3),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reveal only when the selection changes
  }, [selectedId]);

  function focusUnit(id: string | undefined) {
    if (!id) return;
    setFocusId(id);
    scroller.current?.querySelector<SVGGElement>(`[data-unit="${id}"]`)?.focus();
  }
  function onKey(event: KeyboardEvent, node: PlacedNode<OrgUnit>) {
    const { unit } = node;
    const siblings = layout.nodes
      .filter((other) => other.unit.parent_id === unit.parent_id && other.depth === node.depth)
      .sort((left, right) => left.x - right.x);
    const position = siblings.findIndex((other) => other.unit.id === unit.id);
    const actions: Record<string, () => void> = {
      Enter: () => onSelect(unit.id),
      " ": () => (node.hasChildren ? onToggle(unit.id) : onSelect(unit.id)),
      ArrowUp: () => focusUnit(unit.parent_id ?? undefined),
      ArrowDown: () => {
        if (collapsed.has(unit.id) && node.hasChildren) onToggle(unit.id);
        else focusUnit(layout.edges.find((edge) => edge.from === unit.id)?.to);
      },
      ArrowLeft: () => focusUnit(siblings[position - 1]?.unit.id),
      ArrowRight: () => focusUnit(siblings[position + 1]?.unit.id),
      Home: () => focusUnit(layout.nodes.find((other) => other.depth === 0)?.unit.id),
    };
    const run = actions[event.key];
    if (!run) return;
    event.preventDefault();
    run();
  }
  function fit() {
    setZoom(fitScale(layout.width + PADDING * 2, scroller.current?.clientWidth ?? 0));
  }
  if (!units.length)
    return <EmptyState title="No units to show">Create the first unit, or show closed units.</EmptyState>;
  return (
    <section className="org-chart" aria-label="Organisation chart">
      <div className="org-chart__tools">
        <Button icon="minus" onClick={() => setZoom((value) => Math.max(0.2, value / STEP))}>
          Zoom out
        </Button>
        <Button icon="plus" onClick={() => setZoom((value) => Math.min(2, value * STEP))}>
          Zoom in
        </Button>
        <Button onClick={fit}>Fit to screen</Button>
        <Button onClick={() => rest.onCollapseAll(true)}>Collapse all</Button>
        <Button onClick={() => rest.onCollapseAll(false)}>Expand all</Button>
        <span className="org-chart__zoom">Zoom {Math.round(zoom * 100)}%</span>
      </div>
      <div className="org-chart__scroll" ref={scroller}>
        <svg
          className="org-chart__svg"
          width={(layout.width + PADDING * 2) * zoom}
          height={(layout.height + PADDING * 2) * zoom}
          viewBox={`${-PADDING} ${-PADDING} ${layout.width + PADDING * 2} ${layout.height + PADDING * 2}`}
          role="tree"
          aria-label="Organisation units"
        >
          <g aria-hidden="true" className="org-chart__edges">
            {layout.edges.map((edge) => {
              const from = byId.get(edge.from);
              const to = byId.get(edge.to);
              return from && to ? <path key={edge.to} d={connector(from, to)} /> : null;
            })}
          </g>
          <g role="group">
            {layout.nodes.map((node) => (
              <Node
                key={node.unit.id}
                node={node}
                selected={node.unit.id === selectedId}
                focusable={node.unit.id === focusable}
                collapsed={collapsed.has(node.unit.id)}
                over={overId === node.unit.id}
                onSelect={onSelect}
                onToggle={onToggle}
                onKey={onKey}
                onDragStart={rest.onDragStart}
                wasDrag={rest.wasDrag}
              />
            ))}
          </g>
        </svg>
      </div>
    </section>
  );
}
