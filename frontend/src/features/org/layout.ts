/** Pure tree layout for the organisation chart: leaves take consecutive slots, parents centre. */
export const NODE_WIDTH = 208;
export const NODE_HEIGHT = 84;
export const GAP_X = 24;
export const GAP_Y = 56;

type Item = { id: string; parent_id: string | null; name: string };
export type PlacedNode<T extends Item> = {
  unit: T;
  x: number;
  y: number;
  depth: number;
  hasChildren: boolean;
};
export type Edge = { from: string; to: string };
export type Layout<T extends Item> = {
  nodes: PlacedNode<T>[];
  edges: Edge[];
  width: number;
  height: number;
};

function childrenByParent<T extends Item>(units: T[]): { roots: T[]; children: Map<string, T[]> } {
  const ids = new Set(units.map((unit) => unit.id));
  const children = new Map<string, T[]>();
  const roots: T[] = [];
  for (const unit of units) {
    if (unit.parent_id && ids.has(unit.parent_id)) {
      const list = children.get(unit.parent_id) ?? [];
      list.push(unit);
      children.set(unit.parent_id, list);
    } else roots.push(unit);
  }
  const byName = (left: T, right: T) =>
    left.name.localeCompare(right.name) || left.id.localeCompare(right.id);
  roots.sort(byName);
  for (const list of children.values()) list.sort(byName);
  return { roots, children };
}

/** Place every unit not hidden below a collapsed unit. Runs in time linear in the unit count. */
export function layoutTree<T extends Item>(units: T[], collapsed: ReadonlySet<string>): Layout<T> {
  const { roots, children } = childrenByParent(units);
  const nodes: PlacedNode<T>[] = [];
  const edges: Edge[] = [];
  const slot = new Map<string, number>();
  const visit = new Map<string, number>();
  let nextSlot = 0;
  let deepest = 0;
  // Iterative post-order: a unit is centred once all of its visible children have a slot.
  const stack: { unit: T; depth: number; visited: boolean }[] = roots
    .map((unit) => ({ unit, depth: 0, visited: false }))
    .reverse();
  while (stack.length) {
    const entry = stack.pop();
    if (!entry) break;
    const { unit, depth } = entry;
    if (!entry.visited) visit.set(unit.id, visit.size);
    const kids = collapsed.has(unit.id) ? [] : (children.get(unit.id) ?? []);
    if (!entry.visited && kids.length) {
      stack.push({ unit, depth, visited: true });
      for (const kid of [...kids].reverse()) stack.push({ unit: kid, depth: depth + 1, visited: false });
      continue;
    }
    const first = kids[0];
    const last = kids[kids.length - 1];
    const position = first && last ? ((slot.get(first.id) ?? 0) + (slot.get(last.id) ?? 0)) / 2 : nextSlot++;
    slot.set(unit.id, position);
    deepest = Math.max(deepest, depth);
    for (const kid of kids) edges.push({ from: unit.id, to: kid.id });
    nodes.push({
      unit,
      depth,
      hasChildren: (children.get(unit.id) ?? []).length > 0,
      x: position * (NODE_WIDTH + GAP_X),
      y: depth * (NODE_HEIGHT + GAP_Y),
    });
  }
  // Document order (a unit before its sub-units) is the order screen readers and Tab follow.
  nodes.sort((left, right) => (visit.get(left.unit.id) ?? 0) - (visit.get(right.unit.id) ?? 0));
  const columns = Math.max(nextSlot, 1);
  return {
    nodes,
    edges,
    width: columns * NODE_WIDTH + (columns - 1) * GAP_X,
    height: (deepest + 1) * NODE_HEIGHT + deepest * GAP_Y,
  };
}

/** The unit's ancestors, nearest first. Cycles cannot exist on the server; the guard is cheap. */
export function ancestorIds(units: Item[], id: string): string[] {
  const parents = new Map(units.map((unit) => [unit.id, unit.parent_id]));
  const found: string[] = [];
  let current = parents.get(id) ?? null;
  while (current && !found.includes(current)) {
    found.push(current);
    current = parents.get(current) ?? null;
  }
  return found;
}

/** Every unit below the given one, so a "move beneath" choice can leave them out. */
export function descendantIds(units: Item[], id: string): Set<string> {
  const { children } = childrenByParent(units);
  const found = new Set<string>();
  const queue = [id];
  while (queue.length) {
    for (const kid of children.get(queue.pop() ?? "") ?? []) {
      found.add(kid.id);
      queue.push(kid.id);
    }
  }
  return found;
}

/** Collapse state after revealing a unit: only its ancestors are opened. */
export function reveal(collapsed: ReadonlySet<string>, units: Item[], id: string): Set<string> {
  const open = new Set(ancestorIds(units, id));
  return new Set([...collapsed].filter((item) => !open.has(item)));
}

/** Case-insensitive match on unit name or code; blank matches nothing. */
export function matchUnits<T extends Item & { code: string | null }>(units: T[], query: string): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  return units.filter(
    (unit) => unit.name.toLowerCase().includes(needle) || (unit.code ?? "").toLowerCase().includes(needle),
  );
}

/** Scale at which the whole chart fits the available width, never enlarging past real size. */
export function fitScale(layoutWidth: number, available: number): number {
  if (layoutWidth <= 0 || available <= 0) return 1;
  return Math.min(1, Math.max(0.2, available / layoutWidth));
}

/** Unit paths such as "Materials Group / Surface Science Division", for plain-word choices. */
export function unitPath(units: Item[], id: string): string {
  const byId = new Map(units.map((unit) => [unit.id, unit]));
  return [id, ...ancestorIds(units, id)]
    .reverse()
    .map((item) => byId.get(item)?.name ?? "")
    .filter(Boolean)
    .join(" / ");
}
