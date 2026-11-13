import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BASE } from "../../config";
import { fmtTime } from "../../format";
import { useSession } from "../../session";
import { Banner, Button, DataTable, ErrorState, PageHeader, Select, type Column } from "../../ui";
import { usePolledData } from "../admin/usePolledData";
import { FeedbackDetailDrawer } from "./FeedbackDetail";
import { CATEGORY_OPTIONS, STATUS_OPTIONS, categoryWord, mailSentence, statusWord } from "./model";
import type { FeedbackPageData, FeedbackSummary } from "./types";
import "./feedback.css";

const POLL_MS = 30_000;
const FILTERS = ["status", "category"];

function url(params: URLSearchParams): string {
  const query = new URLSearchParams();
  for (const key of [...FILTERS, "cursor"]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  const text = query.toString();
  return text ? `/admin/feedback?${text}` : "/admin/feedback";
}

function columns(
  timezone: string,
  configured: boolean,
  onOpen: (id: string) => void,
): Column<FeedbackSummary>[] {
  return [
    { key: "time", header: "Time", render: (row) => fmtTime(row.created_at, timezone) },
    { key: "from", header: "From", render: (row) => row.username },
    { key: "category", header: "Kind", render: (row) => categoryWord(row.category) },
    {
      key: "page",
      header: "Page",
      render: (row) => (
        <Button
          variant="quiet"
          size="sm"
          aria-label={`Open feedback from ${row.username}`}
          onClick={() => onOpen(row.id)}
        >
          {row.route ?? "Not given"}
        </Button>
      ),
    },
    { key: "status", header: "Status", render: (row) => statusWord(row.status) },
    { key: "files", header: "Files", align: "end", render: (row) => row.attachment_count },
    { key: "email", header: "E-mail", render: (row) => mailSentence(row.email, configured) },
  ];
}

/** Everything people sent with the Feedback button. Administrators may read it: the sender chose that. */
export function FeedbackPage() {
  const { session } = useSession();
  const [params, setParams] = useSearchParams();
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const { data, error, loading, reload } = usePolledData<FeedbackPageData>(url(params), POLL_MS, onDenied);
  const change = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== "cursor") next.delete("cursor");
      if (key !== "item") next.delete("item");
      return next;
    });
  const pick = (key: string) => ({
    value: params.get(key) ?? "",
    onChange: (event: { target: { value: string } }) => change(key, event.target.value),
  });
  const timezone = session?.timezone ?? "UTC";
  const header = (
    <PageHeader
      title="Feedback"
      scope="Messages people sent with the Feedback button. Administrators read these because the sender chose to send them."
      helpHref={`${BASE}/help/admin/feedback`}
      action={
        <Button icon="refresh" onClick={reload}>
          Refresh
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
          message="Feedback has been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );
  const openId = params.get("item");
  return (
    <>
      {header}
      {data && !data.email.configured && (
        <Banner level="warning">
          E-mail not configured. Feedback is saved here, but no e-mail copy is sent until the server is set
          up.
        </Banner>
      )}
      {data && data.email.failed > 0 && (
        <Banner level="warning">
          {data.email.failed} e-mails could not be sent. Open the message to see why and send it again.
        </Banner>
      )}
      <section aria-label="Feedback filters" className="feedback-filters">
        <Select label="Status" placeholder="Any status" options={STATUS_OPTIONS} {...pick("status")} />
        <Select label="Kind" placeholder="Any kind" options={CATEGORY_OPTIONS} {...pick("category")} />
      </section>
      {error && !data ? (
        <ErrorState message={error} onRetry={reload} />
      ) : (
        <DataTable
          caption="Feedback, newest first"
          columns={columns(timezone, data?.email.configured ?? false, (id) => change("item", id))}
          rows={data?.items ?? []}
          rowKey={(row) => row.id}
          loading={loading}
          empty={{
            title: "No feedback here",
            body: "Nothing matches these filters. Clear them to see everything people have sent.",
            action: (
              <Button
                onClick={() =>
                  setParams((previous) => {
                    const next = new URLSearchParams(previous);
                    for (const key of [...FILTERS, "cursor", "item"]) next.delete(key);
                    return next;
                  })
                }
              >
                Clear feedback filters
              </Button>
            ),
          }}
          footer={
            <div className="feedback-actions">
              {params.get("cursor") && <Button onClick={() => change("cursor", "")}>Newest feedback</Button>}
              {data?.next_cursor && (
                <Button onClick={() => change("cursor", data.next_cursor ?? "")}>Older feedback</Button>
              )}
            </div>
          }
        />
      )}
      {openId && (
        <FeedbackDetailDrawer
          key={openId}
          id={openId}
          timezone={timezone}
          emailConfigured={data?.email.configured ?? false}
          onClose={() => change("item", "")}
          onChanged={reload}
        />
      )}
    </>
  );
}
