import { Link } from "react-router-dom";
import { fmtBytes, fmtTime } from "../../format";
import { Button, Card, ErrorState, PageHeader, Skeleton, StatusPill, type HealthStatus } from "../../ui";
import { useAdminData } from "./useAdminData";

type LastBackup = {
  finished_at: string;
  age_seconds: number;
  result: "success" | "failure";
  size_bytes: number | null;
  verification: "passed" | "failed" | "not_run";
  destination: string;
  schema: string | null;
  release: string | null;
};
type BackupStatus = {
  status: HealthStatus;
  headline: string;
  guidance: string | null;
  checked_at: string;
  healthy_within_hours: number;
  stale_after_hours: number;
  last_backup: LastBackup | null;
};

const VERIFICATION = { passed: "Passed", failed: "Failed", not_run: "Not checked" } as const;

/** "5 hours ago", "2 days ago": whole units, so the age is never mistaken for precision. */
export function formatAge(seconds: number): string {
  if (seconds < 90) return "Just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} hours ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function Details({ backup }: { backup: LastBackup }) {
  return (
    <dl className="admin-facts">
      <dt>Finished</dt>
      <dd>
        {fmtTime(backup.finished_at)} ({formatAge(backup.age_seconds)})
      </dd>
      <dt>Result</dt>
      <dd>{backup.result === "success" ? "Completed" : "Did not complete"}</dd>
      <dt>Size</dt>
      <dd>{backup.size_bytes === null ? "Not recorded" : fmtBytes(backup.size_bytes)}</dd>
      <dt>Verification</dt>
      <dd>{VERIFICATION[backup.verification]}</dd>
      <dt>Kept at</dt>
      <dd>{backup.destination}</dd>
      <dt>Version</dt>
      <dd>{backup.release ?? "Not recorded"}</dd>
    </dl>
  );
}

/** The Backups page (AD-10): what the operator's last receipt says, never implying more. */
export function BackupsPage() {
  const { data, error, reload } = useAdminData<BackupStatus>("/admin/backups/status");
  return (
    <>
      <PageHeader
        title="Backups"
        scope="The last backup recorded by the server. LabAdda does not run backups itself."
        action={
          <Button icon="refresh" onClick={reload}>
            Check again
          </Button>
        }
      />
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        <Skeleton label="Loading backup status" />
      ) : (
        <>
          <Card title="Latest backup">
            <p>
              <StatusPill status={data.status} />
            </p>
            <p>{data.headline}</p>
            {data.guidance && <p>{data.guidance}</p>}
            {data.last_backup && <Details backup={data.last_backup} />}
            <p className="admin-note">
              Checked {fmtTime(data.checked_at)}. A backup is expected at least every{" "}
              {data.healthy_within_hours} hours; after {data.stale_after_hours} hours this page shows it as
              stale.
            </p>
          </Card>
          <Card title="Schedule and practice restores">
            <dl className="admin-facts">
              <dt>Next scheduled backup</dt>
              <dd>Not recorded. The server does not report its timer to this page.</dd>
              <dt>Last restore practice</dt>
              <dd>Not recorded. Practise a restore on the test copy at least once a quarter.</dd>
            </dl>
          </Card>
          <Card title="Guides">
            <ul>
              <li>
                <Link to="/help/admin/backups-page">Reading the Backups page</Link>
              </li>
            </ul>
          </Card>
        </>
      )}
    </>
  );
}
