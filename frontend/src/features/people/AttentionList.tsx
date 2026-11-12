import { Link } from "react-router-dom";
import { ErrorState, Skeleton, Tag } from "../../ui";
import { usePeopleData } from "./usePeopleData";
import type { AttentionItem } from "./changeTypes";

const TONES = { critical: "danger", error: "danger", warning: "warn", info: "neutral" } as const;

/** What needs an administrator's decision, each with the page that fixes it (PO-22). */
export function AttentionList({ onDenied }: { onDenied: () => void }) {
  const list = usePeopleData<{ items: AttentionItem[] }>("/admin/org/attention", onDenied);
  if (list.error) return <ErrorState message={list.error} onRetry={list.refresh} />;
  if (list.loading) return <Skeleton lines={2} />;
  const items = list.data?.items ?? [];
  return (
    <section aria-label="Needs attention" className="people-attention">
      <h3 className="people-change__heading">Needs attention</h3>
      {items.length ? (
        <ul className="people-history">
          {items.map((item) => (
            <li key={item.id}>
              <Tag tone={TONES[item.severity]}>{item.severity === "info" ? "Notice" : "Attention"}</Tag>{" "}
              <strong>{item.title}</strong>
              <br />
              <span>{item.detail}</span>
              <br />
              <Link to={item.route}>Open the page that fixes this</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p>Nothing needs attention.</p>
      )}
    </section>
  );
}
