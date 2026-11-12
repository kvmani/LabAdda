import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { BASE } from "../../config";
import { Button, ErrorState, PageHeader } from "../../ui";
import { peopleUrl } from "./model";
import { usePeopleNavigation } from "./usePeopleNavigation";
import { usePeopleData } from "./usePeopleData";
import { PeopleFilters } from "./PeopleFilters";
import { PeopleTable } from "./PeopleTable";
import { StaffProfile } from "./StaffProfile";
import { ExportReport } from "./ExportReport";
import { AddPersonDialog } from "./AddPersonDialog";
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
  const units = usePeopleData<{ workspaces: Unit[] }>("/admin/workspaces", onDenied);
  const identity = params.get("person");
  const [adding, setAdding] = useState(false);
  const unitList = units.data?.workspaces ?? null;
  return (
    <>
      <PeopleHeader
        reportUrl={peopleUrl(params, true)}
        onDenied={onDenied}
        onAdd={unitList ? () => setAdding(true) : undefined}
      />
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
          onChanged={directory.refresh}
        />
      )}
    </>
  );
}

function PeopleHeader({
  reportUrl,
  onDenied,
  onAdd,
}: {
  reportUrl: string;
  onDenied: () => void;
  onAdd?: () => void;
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
          <Link to="/admin/people/basic">Basic account tools</Link>
          <ExportReport key={reportUrl} url={reportUrl} onDenied={onDenied} />
        </div>
      }
    />
  );
}
