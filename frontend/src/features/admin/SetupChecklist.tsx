import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { BASE } from "../../config";
import { Button, Card, ErrorState, PageHeader, Skeleton, StatusPill } from "../../ui";
import { usePolledData } from "./usePolledData";
import "./setup.css";

export type SetupState = "done" | "not_done" | "unknown";
export type SetupItem = {
  key: string;
  label: string;
  state: SetupState;
  detail: string;
  screen: string;
  help: string;
};
export type SetupChecklistData = { checked_at: string; done: number; total: number; items: SetupItem[] };

const POLL_MS = 30000;
const PILL = {
  done: { tone: "ok", icon: "success", label: "Done" },
  not_done: { tone: "warn", icon: "warning", label: "Not done" },
  unknown: { tone: "neutral", icon: "help", label: "Unknown" },
} as const;

function Item({ item }: { item: SetupItem }) {
  return (
    <li className="setup-item">
      <div className="setup-item__head">
        <StatusPill {...PILL[item.state]} />
        <p className="setup-item__title">{item.label}</p>
      </div>
      <p className="setup-item__detail">{item.detail}</p>
      <p className="setup-item__links">
        <Link to={item.screen} aria-label={`Open the page for: ${item.label}`}>
          Open the page
        </Link>
        <Link to={`/help/${item.help}`} aria-label={`Read the help for: ${item.label}`}>
          Read the help
        </Link>
      </p>
    </li>
  );
}

/** The new-site checklist (HP-07). Every state comes from the server; nothing here can be ticked. */
export function SetupChecklist() {
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const { data, error, reload } = usePolledData<SetupChecklistData>(
    "/admin/setup-checklist",
    POLL_MS,
    onDenied,
  );
  const header = (
    <PageHeader
      title="Setting up this site"
      scope="What a new installation needs. Each line is checked against the real state of the site."
      helpHref={`${BASE}/help/admin/setup-checklist`}
      action={
        <Button icon="refresh" onClick={reload}>
          Check again
        </Button>
      }
    />
  );
  if (denied)
    return (
      <>
        {header}
        <ErrorState
          title="Your administration access changed"
          message="The checklist has been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );
  if (error && !data)
    return (
      <>
        {header}
        <ErrorState message={error} onRetry={reload} />
      </>
    );
  if (!data)
    return (
      <>
        {header}
        <Skeleton label="Loading the setup checklist" />
      </>
    );
  return (
    <>
      {header}
      {error && (
        <p className="setup-warning" role="alert">
          The checklist could not be refreshed. The lines below may be out of date.
        </p>
      )}
      <Card title={`${data.done} of ${data.total} done`}>
        <ol className="setup-list" aria-label="Setup checklist">
          {data.items.map((item) => (
            <Item key={item.key} item={item} />
          ))}
        </ol>
        <p className="setup-note">
          A line is only Done when the site shows it is true. Unknown means the site cannot tell yet; it is
          never counted as done.
        </p>
      </Card>
    </>
  );
}
