import { ErrorState, Select, Skeleton } from "../../ui";
import { usePeopleData } from "./usePeopleData";
import type { Candidates } from "./changeTypes";

/** Choose a successor by name from the people the server says belong to that workspace. */
export function SuccessorPicker({
  workspaceId,
  label,
  named = false,
  value,
  exclude,
  onChange,
  onDenied,
}: {
  workspaceId: string;
  label: string;
  /** Add the workspace's name to the label, e.g. "New steward of" + name. */
  named?: boolean;
  value: string;
  exclude?: string;
  onChange: (id: string) => void;
  onDenied: () => void;
}) {
  const result = usePeopleData<Candidates>(
    `/admin/changes/candidates?workspace_id=${encodeURIComponent(workspaceId)}`,
    onDenied,
  );
  if (result.error) return <ErrorState message={result.error} onRetry={result.refresh} />;
  if (!result.data) return <Skeleton label={`Loading people for ${label.toLowerCase()}`} />;
  const options = result.data.people
    .filter((person) => person.id !== exclude)
    .map((person) => ({
      value: person.id,
      label: person.role ? `${person.display_name} (${person.role})` : person.display_name,
    }));
  const scope = result.data.workspace.kind === "org" ? "people of this unit" : "its active members";
  return (
    <Select
      label={named ? `${label} ${result.data.workspace.name}` : label}
      hint={`Only ${scope} are listed.${result.data.truncated ? " The first 200 by name are shown." : ""}`}
      placeholder={options.length ? "Choose a person" : "No one is available"}
      options={options}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
