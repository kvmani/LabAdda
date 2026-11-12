import { Card, EmptyState, Tag } from "../../ui";
import type { OrgSpace } from "./types";

/** Projects and groups sit beside the chart, not in it: names, stewards and member counts only. */
export function SpacesList({ spaces }: { spaces: OrgSpace[] }) {
  return (
    <Card title="Projects and groups">
      {spaces.length ? (
        <ul className="org-spaces">
          {spaces.map((space) => (
            <li key={space.id}>
              <strong>{space.name}</strong> <Tag>{space.kind === "project" ? "Project" : "Group"}</Tag>
              {space.archived && <Tag tone="warn">Archived</Tag>}
              <span className="org-spaces__meta">
                {space.stewards.length
                  ? `Steward: ${space.stewards.map((item) => item.name).join(", ")}`
                  : "No active steward"}
                {" · "}
                {space.members} {space.members === 1 ? "member" : "members"}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="None yet">No projects or groups exist.</EmptyState>
      )}
    </Card>
  );
}
