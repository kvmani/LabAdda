import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BASE } from "../../config";
import { useSession } from "../../session";
import { ErrorState, PageHeader, type SelectOption } from "../../ui";
import { unitOptions } from "../people/model";
import type { Unit } from "../people/types";
import { AuditDetail } from "./AuditDetail";
import { AuditFilters } from "./AuditFilters";
import { AuditTable } from "./AuditTable";
import { ExportAudit } from "./ExportAudit";
import { FILTER_KEYS, auditUrl } from "./model";
import type { AuditPage as Page, PersonOption } from "./types";
import { useAuditData } from "./useAuditData";
import "./audit.css";

/** Authority loss unmounts every record so nothing stale stays readable. */
export function AuditPage() {
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  if (denied)
    return (
      <ErrorState
        title="Your administration access changed"
        message="Audit entries have been cleared. Reload to check access again."
        onRetry={() => window.location.reload()}
        retryLabel="Check administration access"
      />
    );
  return <AuditExplorer onDenied={onDenied} />;
}

function useAuditParams() {
  const [params, setParams] = useSearchParams();
  const change = (key: string, value: string) => {
    if ((params.get(key) ?? "") === value) return;
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== "cursor") next.delete("cursor");
      if (key !== "entry") next.delete("entry");
      return next;
    });
  };
  const reset = () =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      for (const key of [...FILTER_KEYS, "cursor", "entry"]) next.delete(key);
      return next;
    });
  return { params, change, reset };
}

function AuditExplorer({ onDenied }: { onDenied: () => void }) {
  const { session } = useSession();
  const { params, change, reset } = useAuditParams();
  const page = useAuditData<Page>(auditUrl(params), onDenied);
  const people = useAuditData<{ users: PersonOption[] }>("/admin/users", onDenied);
  const units = useAuditData<{ workspaces: Unit[] }>("/admin/workspaces", onDenied);
  const unitChoices = useMemo<SelectOption[] | null>(
    () => (units.data ? unitOptions(units.data.workspaces) : null),
    [units.data],
  );
  const timezone = session?.timezone ?? "UTC";
  const open = page.data?.events.find((event) => String(event.id) === params.get("entry"));
  const lookupError = people.error || units.error;
  return (
    <>
      <PageHeader
        title="Audit"
        scope="Who changed what, and when. Names, times and reasons only; private work is never shown."
        helpHref={BASE + "/admin/help"}
        action={<ExportAudit key={auditUrl(params, true)} url={auditUrl(params, true)} onDenied={onDenied} />}
      />
      <AuditFilters
        params={params}
        people={people.data?.users ?? null}
        units={unitChoices}
        lookupError={lookupError}
        onRetryLookups={() => {
          people.refresh();
          units.refresh();
        }}
        resultCount={
          page.data && !page.data.next_cursor && !params.has("cursor") ? page.data.events.length : null
        }
        onChange={change}
        onReset={reset}
      />
      {page.error ? (
        <ErrorState message={page.error} onRetry={page.refresh} />
      ) : (
        <AuditTable
          data={page.data}
          loading={page.loading}
          timezone={timezone}
          onOpen={(id) => change("entry", String(id))}
          onNext={(cursor) => change("cursor", cursor)}
          onFirst={() => change("cursor", "")}
          hasCursor={params.has("cursor")}
          onReset={reset}
        />
      )}
      {open && <AuditDetail event={open} timezone={timezone} onClose={() => change("entry", "")} />}
    </>
  );
}
