import { useLocation, useNavigate } from "react-router-dom";
import { treeOrder } from "../../workspaces";
import type { Workspace } from "../../types";

/** Personal pages offered by the switcher; values are stable because browser checks select them. */
const PERSONAL: { value: string; label: string; to: string }[] = [
  { value: "whiteboard", label: "My Whiteboard (private)", to: "/whiteboard" },
  { value: "today", label: "My day", to: "/today" },
  { value: "preferences", label: "Alert preferences", to: "/preferences" },
  { value: "private_conversation", label: "Private conversation", to: "/groups/new?conversation=1" },
  { value: "new_group", label: "New group", to: "/groups/new" },
  { value: "notes", label: "My Notes", to: "/notes" },
  { value: "usage", label: "My storage usage", to: "/usage" },
];

function selectedValue(pathname: string, search: string, currentId: string | undefined): string {
  if (currentId) return currentId;
  if (pathname === "/groups/new")
    return search.includes("conversation=1") ? "private_conversation" : "new_group";
  if (pathname === "/operations") return "operations";
  return PERSONAL.find((page) => page.to === pathname)?.value ?? "";
}

type WorkspaceSwitcherProps = { workspaces: Workspace[]; currentId: string | undefined; operations: boolean };

/** On narrow screens the rail becomes this labelled drop-down (UX-03). */
export function WorkspaceSwitcher({ workspaces, currentId, operations }: WorkspaceSwitcherProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const projects = workspaces.filter((workspace) => workspace.kind === "project");
  const groups = workspaces.filter((workspace) => workspace.kind === "group");
  const pages = operations
    ? [...PERSONAL, { value: "operations", label: "Operational observations", to: "/operations" }]
    : PERSONAL;
  return (
    <label className="shell-switcher">
      <span className="ui-visually-hidden">Switch workspace</span>
      <select
        aria-label="Switch workspace"
        className="ui-input"
        value={selectedValue(location.pathname, location.search, currentId)}
        onChange={(event) => {
          const value = event.target.value;
          if (!value) return;
          navigate(pages.find((page) => page.value === value)?.to ?? `/w/${value}/noticeboard`);
        }}
      >
        <option value="">Choose workspace…</option>
        {treeOrder(workspaces).map(({ ws, depth }) => (
          <option key={ws.id} value={ws.id}>
            {"· ".repeat(depth) + ws.name}
          </option>
        ))}
        {projects.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            Project: {workspace.name}
          </option>
        ))}
        {groups.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            Group: {workspace.name}
          </option>
        ))}
        {pages.map((page) => (
          <option key={page.value} value={page.value}>
            {page.label}
          </option>
        ))}
      </select>
    </label>
  );
}
