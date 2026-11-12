import { useCallback, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { BASE } from "../../config";
import { Button, ErrorState, PageHeader } from "../../ui";
import { peopleUrl } from "./model";
import { usePeopleNavigation } from "./usePeopleNavigation";
import { usePeopleData } from "./usePeopleData";
import { PeopleFilters } from "./PeopleFilters";
import { PeopleTable } from "./PeopleTable";
import { StaffProfile } from "./StaffProfile";
import { AttentionList } from "./AttentionList";
import { ScheduledChanges } from "./ScheduledChanges";
import { ExportReport } from "./ExportReport";
import { AddPersonDialog } from "./AddPersonDialog";
import { BulkActions, MAX_SELECTED } from "./BulkActions";
import { ImportDialog } from "./ImportDialog";
import type { ConsoleAccess } from "../admin/console";
import type { OrgTree } from "../org/types";
import type { Directory, Unit } from "./types";
import "./people.css";

/** Authority loss unmounts every metadata region, invalidating pending responses together. */
export function PeoplePage() {
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  if (denied)
    return (
      <ErrorState
        title="Your administration access changed"
        message="Staff records have been cleared. Reload to check access again."
        onRetry={() => window.location.reload()}
        retryLabel="Check administration access"
      />
    );
  return <PeopleDirectory onDenied={onDenied} />;
}
function PeopleDirectory({ onDenied }: { onDenied: () => void }) {
  const { params, change, reset, profile } = usePeopleNavigation();
  const directory = usePeopleData<Directory>(peopleUrl(params), onDenied);
  // A unit administrator reaches only their branch: its units come from the scoped chart, and the
  // site-wide tools (import, attention list, basic account tools, appointments) are not offered.
  const unitAdmin = useOutletContext<ConsoleAccess | null>()?.unit_admin ?? false;
  const siteUnits = usePeopleData<{ workspaces: Unit[] }>(unitAdmin ? null : "/admin/workspaces", onDenied);
  const branch = usePeopleData<OrgTree>(unitAdmin ? "/admin/org/tree" : null, onDenied);
  const units = unitAdmin
    ? {
        ...branch,
        data: branch.data && {
          workspaces: branch.data.units.map((unit): Unit => ({
            id: unit.id,
            name: unit.name,
            kind: "org",
            parent_id: unit.parent_id,
            archived: unit.archived,
          })),
        },
      }
    : siteUnits;
  const identity = params.get("person");
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [listVersion, setListVersion] = useState(0);
  const refreshAll = () => {
    directory.refresh();
    setListVersion((version) => version + 1);
  };
  function select(id: string, on: boolean) {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    setSelected(next);
  }
  const unitList = units.data?.workspaces ?? null;
  return (
    <>
      <PeopleHeader
        reportUrl={peopleUrl(params, true)}
        onDenied={onDenied}
        onAdd={unitList ? () => setAdding(true) : undefined}
        onImport={unitAdmin ? undefined : () => setImporting(true)}
        basicTools={!unitAdmin}
      />
      {importing && (
        <ImportDialog onClose={() => setImporting(false)} onDenied={onDenied} onDone={directory.refresh} />
      )}
      {adding && unitList && (
        <AddPersonDialog
          units={unitList}
          onClose={() => setAdding(false)}
          onDenied={onDenied}
          onAdded={(id) => {
            directory.refresh();
            profile("person", id);
          }}
        />
      )}
      {unitList && (
        <BulkActions
          selected={[...selected]}
          units={unitList}
          onClear={() => setSelected(new Set())}
          onDenied={onDenied}
          onDone={directory.refresh}
        />
      )}
      {!unitAdmin && <AttentionList key={`attention-${listVersion}`} onDenied={onDenied} />}
      <ScheduledChanges key={`scheduled-${listVersion}`} onDenied={onDenied} onChanged={refreshAll} />
      <PeopleFilters
        params={params}
        units={units.data?.workspaces ?? null}
        unitError={units.error}
        onRetryUnits={units.refresh}
        resultCount={
          directory.data && !directory.data.next_cursor && !params.has("cursor")
            ? directory.data.people.length
            : null
        }
        onChange={change}
        onReset={reset}
      />
      <Button variant="quiet" icon="refresh" onClick={directory.refresh}>
        Refresh directory
      </Button>
      {directory.error ? (
        <ErrorState message={directory.error} onRetry={directory.refresh} />
      ) : (
        <PeopleTable
          data={directory.data}
          loading={directory.loading}
          onOpen={(id) => profile("person", id)}
          onNext={(cursor) => change("cursor", cursor)}
          onFirst={() => change("cursor", "")}
          hasCursor={params.has("cursor")}
          selected={selected}
          onSelect={select}
          selectionFull={selected.size >= MAX_SELECTED}
          onReset={reset}
        />
      )}
      {identity && (
        <StaffProfile
          key={identity}
          identity={identity}
          view={params.get("view") ?? "record"}
          onView={(view) => profile("view", view)}
          onClose={() => profile("person")}
          onDenied={onDenied}
          units={unitList}
          canAppoint={!unitAdmin}
          onChanged={refreshAll}
        />
      )}
    </>
  );
}

function PeopleHeader({
  reportUrl,
  onDenied,
  onAdd,
  onImport,
  basicTools,
}: {
  reportUrl: string;
  onDenied: () => void;
  onAdd?: () => void;
  onImport?: () => void;
  basicTools: boolean;
}) {
  return (
    <PageHeader
      title="People"
      scope="Read staff records and recorded access without opening private work."
      helpHref={BASE + "/admin/help"}
      action={
        <div className="people-actions">
          <Button variant="primary" icon="plus" onClick={onAdd} disabled={!onAdd}>
            Add person
          </Button>
          {onImport && (
            <Button icon="plus" onClick={onImport}>
              Import staff list
            </Button>
          )}
          {basicTools && <Link to="/admin/people/basic">Basic account tools</Link>}
          <ExportReport key={reportUrl} url={reportUrl} onDenied={onDenied} />
        </div>
      }
    />
  );
}
