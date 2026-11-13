import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { Badge, Tag } from "../../ui";
import { treeOrder } from "../../workspaces";
import type { Workspace } from "../../types";

/** Deepest indentation step; deeper units keep this indent so names stay readable. */
const MAX_DEPTH = 6;

function WorkspaceLink({
  workspace,
  depth,
  current,
}: {
  workspace: Workspace;
  depth: number;
  current: boolean;
}) {
  return (
    <li>
      <NavLink
        to={`/w/${workspace.id}/noticeboard`}
        className={`shell-rail__link shell-rail__link--depth-${Math.min(depth, MAX_DEPTH)}`}
        aria-current={current ? "page" : undefined}
        title={workspace.name}
      >
        <span className="shell-rail__name">{workspace.name}</span>
        {workspace.archived && <Tag>Archived</Tag>}
        <Badge count={workspace.unread_chat} label="unread chat messages" />
      </NavLink>
    </li>
  );
}

function PersonalLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <li>
      <NavLink to={to} end className="shell-rail__link">
        {children}
      </NavLink>
    </li>
  );
}

type RailNavProps = {
  workspaces: Workspace[];
  currentId: string | undefined;
  operations: boolean;
  error: string | null;
};

/** The left rail: personal pages, then the units, projects and groups this person can open. */
export function RailNav({ workspaces, currentId, operations, error }: RailNavProps) {
  const tree = treeOrder(workspaces);
  const projects = workspaces.filter((workspace) => workspace.kind === "project");
  const groups = workspaces.filter((workspace) => workspace.kind === "group");
  return (
    <nav className="shell-rail" aria-label="Workspaces">
      <h2 className="shell-rail__heading">Personal</h2>
      <ul>
        <PersonalLink to="/today">My day</PersonalLink>
        <PersonalLink to="/my-tasks">My Tasks</PersonalLink>
        <PersonalLink to="/todos">
          <span className="shell-rail__name">My To-do Lists</span> <Tag>private</Tag>
        </PersonalLink>
        <PersonalLink to="/whiteboard">
          My Whiteboard <Tag>private</Tag>
        </PersonalLink>
        <PersonalLink to="/notes">
          <span className="shell-rail__name">My Notes</span> <Tag>private</Tag>
        </PersonalLink>
        <PersonalLink to="/preferences">Alert preferences</PersonalLink>
        <PersonalLink to="/usage">My storage usage</PersonalLink>
        {operations && <PersonalLink to="/operations">Operational observations</PersonalLink>}
      </ul>
      {error && (
        <p className="shell-rail__error" role="alert">
          {error}
        </p>
      )}
      {tree.length > 0 && (
        <>
          <h2 className="shell-rail__heading">Organization</h2>
          <ul>
            {tree.map(({ ws, depth }) => (
              <WorkspaceLink key={ws.id} workspace={ws} depth={depth} current={ws.id === currentId} />
            ))}
          </ul>
        </>
      )}
      {projects.length > 0 && (
        <>
          <h2 className="shell-rail__heading">Projects</h2>
          <ul>
            {projects.map((workspace) => (
              <WorkspaceLink
                key={workspace.id}
                workspace={workspace}
                depth={0}
                current={workspace.id === currentId}
              />
            ))}
          </ul>
        </>
      )}
      <h2 className="shell-rail__heading">My groups</h2>
      {groups.length > 0 ? (
        <ul>
          {groups.map((workspace) => (
            <WorkspaceLink
              key={workspace.id}
              workspace={workspace}
              depth={0}
              current={workspace.id === currentId}
            />
          ))}
        </ul>
      ) : (
        <p className="shell-rail__empty">You are not in any groups yet.</p>
      )}
      <ul className="shell-rail__actions">
        <li>
          <NavLink to="/groups/new" end className="shell-rail__action">
            + New group
          </NavLink>
        </li>
        <li>
          <NavLink to="/groups/new?conversation=1" className="shell-rail__action">
            + Private conversation
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}
