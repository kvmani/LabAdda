import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { api, errorMessage } from "../api";
import { fmtBytes } from "../format";
import type { WorkspaceUsage as Observation } from "../governance-types";
import { LogicalCharges } from "../components/LogicalCharges";
import { Button, Card, ErrorState, Skeleton } from "../ui";
import "./usage.css";

export function WorkspaceUsage({ workspaceId }: { workspaceId: string }) {
  const [data, setData] = useState<Observation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  async function load() {
    const request = ++generation.current;
    setData(null);
    setError("");
    setLoading(true);
    try {
      const result = await api<Observation>(`/workspaces/${workspaceId}/usage`);
      if (request === generation.current) setData(result);
    } catch (e: unknown) {
      if (request === generation.current) setError(errorMessage(e));
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    return () => {
      invalidate(generation);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the workspace changes
  }, [workspaceId]);
  return (
    <section className="usage" aria-labelledby="workspace-usage-heading">
      <div className="usage__head">
        <div>
          <h2 id="workspace-usage-heading" className="usage__title">
            Workspace storage usage
          </h2>
          <p>
            This view covers content owned by this workspace only. Parent and sibling workspaces are measured
            separately.
          </p>
        </div>
        <Button icon="refresh" onClick={load} disabled={loading}>
          Refresh workspace usage
        </Button>
      </div>
      {error && <ErrorState message={error} title="Usage could not be loaded" onRetry={() => void load()} />}
      {loading && <Skeleton lines={5} label="Loading workspace measurements…" />}
      {data && (
        <Card title="Retained workspace files" level={3}>
          <div className="usage__body">
            <dl className="usage__list">
              <dt>Original files retained</dt>
              <dd>
                {fmtBytes(data.files.retained_original_bytes)} · {data.files.retained_files}{" "}
                {data.files.retained_files === 1 ? "file" : "files"}
              </dd>
              <dt>Of those, attached to removed posts</dt>
              <dd>{fmtBytes(data.files.removed_post_original_bytes)}</dd>
              <dt>Previews with recorded measurements</dt>
              <dd>{fmtBytes(data.files.recorded_preview_bytes)}</dd>
              <dt>Previews with unknown measurements</dt>
              <dd>{data.files.unknown_preview_files}</dd>
              <dt>Pending uploads for this workspace</dt>
              <dd>Not attributable before a destination is committed</dd>
              <dt>Workspace budget</dt>
              <dd>Not configured</dd>
              <dt>Observed</dt>
              <dd>{new Date(data.observed_at).toLocaleString()}</dd>
            </dl>
            <LogicalCharges charges={data.logical_charges} scope="workspace" />
            <p className="usage__note">
              Partial observations: retained files can include images no longer shown on the board and
              attachments to removed posts. Recorded preview sizes are not a fresh disk inspection. These
              counters do not activate quotas or retention.
            </p>
            <p>
              Private notes, uploads without a committed destination and physical database overhead are
              excluded. Personal upload limits remain visible in My storage usage.
            </p>
          </div>
        </Card>
      )}
    </section>
  );
}
