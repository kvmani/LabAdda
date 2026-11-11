import { Link } from "react-router-dom";
import { Card, StatusPill, type HealthStatus } from "../../ui";
import { HealthChart } from "./HealthChart";
import { formatAge, formatValue } from "./model";
import type { HealthItem } from "./types";

type Props = { item: HealthItem; status: HealthStatus; ageSeconds: number; now: number };

/** One item: status word, headline figure, plain sentence, freshness, chart and where to read more. */
export function HealthCard({ item, status, ageSeconds, now }: Props) {
  return (
    <Card title={item.label} actions={<StatusPill status={status} />}>
      <p className="health-value">{formatValue(item.value, item.unit)}</p>
      <p className="health-detail">{item.detail}</p>
      <p className="health-checked">Checked {formatAge(ageSeconds)}</p>
      {item.chart && <HealthChart label={item.label} spec={item.chart} now={now} />}
      {status !== "healthy" && (
        <p>
          <Link to={`/help/${item.help}`} aria-label={`What to do: ${item.label}`}>
            What to do
          </Link>
        </p>
      )}
    </Card>
  );
}
