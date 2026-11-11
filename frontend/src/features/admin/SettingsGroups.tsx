import { fmtBytes } from "../../format";
import { Card } from "../../ui";
import type { SettingGroup, SettingItem } from "./settingsTypes";

function shown(item: SettingItem): string {
  if (item.unit === "bytes" && typeof item.value === "number") return fmtBytes(item.value);
  const value =
    typeof item.value === "number" ? item.value.toLocaleString() : String(item.value ?? "Unknown");
  return item.unit ? `${value} ${item.unit}` : value;
}

/** Effective limits in plain words; none of them can be changed from this page. */
export function SettingsGroups({ groups }: { groups: SettingGroup[] }) {
  return (
    <>
      {groups.map((group) => (
        <Card key={group.key} title={group.title}>
          <p className="admin-note">{group.summary}</p>
          <dl className="admin-facts">
            {group.items.map((item) => (
              <div key={item.key} className="admin-facts__row">
                <dt>{item.label}</dt>
                <dd>
                  <strong>{shown(item)}</strong>
                  <br />
                  {item.explanation} <span className="admin-note">{item.changed_by}</span>
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      ))}
    </>
  );
}
