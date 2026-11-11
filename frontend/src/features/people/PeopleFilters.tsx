import { Button, Checkbox, ErrorState, SearchInput, Select } from "../../ui";
import { STATUS_OPTIONS, unitOptions } from "./model";
import type { Unit } from "./types";

type Props = {
  params: URLSearchParams;
  units: Unit[] | null;
  unitError: string;
  onRetryUnits: () => void;
  resultCount: number | null;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
};

/** Filters use explicit home-unit and direct-role wording; every choice lives in the URL. */
export function PeopleFilters({
  params,
  units,
  unitError,
  onRetryUnits,
  resultCount,
  onChange,
  onReset,
}: Props) {
  return (
    <section aria-label="People filters" className="people-filters">
      <SearchInput
        label="Search people"
        value={params.get("q") ?? ""}
        resultCount={resultCount}
        placeholder="Name, username or employee number"
        onSearch={(value) => onChange("q", value)}
      />
      <Select
        label="Employment status"
        placeholder="All statuses"
        options={STATUS_OPTIONS}
        value={params.get("status") ?? ""}
        onChange={(event) => onChange("status", event.target.value)}
      />
      <Select
        label="Home unit"
        placeholder={units ? "All home units" : "Loading units…"}
        disabled={!units}
        options={unitOptions(units ?? [])}
        value={params.get("unit_id") ?? ""}
        onChange={(event) => onChange("unit_id", event.target.value)}
      />
      <OrderingFilters params={params} onChange={onChange} onReset={onReset} />
      {unitError && <ErrorState message={unitError} onRetry={onRetryUnits} />}
    </section>
  );
}

function OrderingFilters({ params, onChange, onReset }: Pick<Props, "params" | "onChange" | "onReset">) {
  return (
    <>
      <Select
        label="Direct access role"
        placeholder="All direct roles"
        value={params.get("role") ?? ""}
        options={[
          { value: "admin", label: "Site administrator" },
          { value: "member", label: "Member" },
          { value: "steward", label: "Steward" },
        ]}
        onChange={(event) => onChange("role", event.target.value)}
      />
      <Select
        label="Sort people by"
        value={params.get("sort") ?? "name"}
        options={[
          { value: "name", label: "Name" },
          { value: "username", label: "Username" },
          { value: "employee_no", label: "Employee number" },
          { value: "status", label: "Employment status" },
          { value: "last_seen_on", label: "Last sign-in date" },
        ]}
        onChange={(event) => onChange("sort", event.target.value)}
      />
      <div className="people-actions">
        <Checkbox
          label="Include sub-units"
          checked={params.get("include_children") !== "false"}
          onChange={(event) => onChange("include_children", event.target.checked ? "" : "false")}
        />
        <Checkbox
          label="Descending order"
          checked={params.get("descending") === "true"}
          onChange={(event) => onChange("descending", event.target.checked ? "true" : "")}
        />
        <Button variant="quiet" onClick={onReset}>
          Clear people filters
        </Button>
      </div>
    </>
  );
}
