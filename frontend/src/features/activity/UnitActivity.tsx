import { BarChart, DataTable, type Column } from "../../ui";
import { categoryFormatter, categorySeries, figureSort, figureText } from "./model";
import type { Units, UnitRow } from "./types";

type Row = Pick<UnitRow, "active_people" | "items_created" | "previous_active_people"> & {
  key: string;
  name: string;
};

const COLUMNS: Column<Row>[] = [
  { key: "name", header: "Unit", render: (row) => row.name, sortValue: (row) => row.name },
  {
    key: "active",
    header: "Active people",
    align: "end",
    render: (row) => figureText(row.active_people),
    sortValue: (row) => figureSort(row.active_people),
  },
  {
    key: "previous",
    header: "Previous period",
    align: "end",
    render: (row) => (row.previous_active_people ? figureText(row.previous_active_people) : "Not measured"),
    sortValue: (row) => figureSort(row.previous_active_people),
  },
  {
    key: "items",
    header: "Items created",
    align: "end",
    render: (row) => figureText(row.items_created),
    sortValue: (row) => figureSort(row.items_created),
  },
];

/** Activity by home unit: suppressed figures arrive without a number and are not charted. */
export function UnitActivity({ units, period, updated }: { units: Units; period: string; updated?: string }) {
  if (units.state === "unknown") return <p role="status">Activity by unit: not measured in this period.</p>;
  const rows: Row[] = units.units.map((unit) => ({ ...unit, key: unit.id }));
  if (units.no_home_unit) rows.push({ ...units.no_home_unit, key: "none", name: "No home unit" });
  return (
    <section className="activity-units" aria-labelledby="activity-units-title">
      <h2 id="activity-units-title" className="activity-section-title">
        Activity by unit
      </h2>
      <p className="activity-note">
        People are counted in their home unit only, not in the units above it. Figures are rounded to the
        nearest {units.rounded_to}. A unit with fewer than {units.minimum_group} active people shows “Fewer
        than {units.minimum_group}” and is left out of the chart; another small unit may be hidden with it so
        that no one person can be worked out. Projects and groups appear only as totals.
      </p>
      {units.chart.length ? (
        <BarChart
          title="Active people by unit"
          series={categorySeries("Active people", units.chart)}
          unit="people"
          period={period}
          updated={updated}
          formatTime={categoryFormatter(units.chart)}
        />
      ) : (
        <p role="status">No unit has enough active people to be shown in a chart for this period.</p>
      )}
      <DataTable
        caption="All units"
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.key}
        empty={{ title: "No organisation units yet" }}
      />
    </section>
  );
}
