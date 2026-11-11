import { Button, DateInput, ErrorState, SearchInput, Select } from "../../ui";
import { GROUP_OPTIONS, OUTCOME_OPTIONS, personOptions } from "./model";
import type { PersonOption } from "./types";
import type { SelectOption } from "../../ui";

type Props = {
  params: URLSearchParams;
  people: PersonOption[] | null;
  units: SelectOption[] | null;
  lookupError: string;
  onRetryLookups: () => void;
  resultCount: number | null;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
};

/** Every choice lives in the URL so a filtered view can be shared and reloaded. */
export function AuditFilters({
  params,
  people,
  units,
  lookupError,
  onRetryLookups,
  resultCount,
  onChange,
  onReset,
}: Props) {
  const choices = people ? personOptions(people) : [];
  const pick = (key: string) => ({
    value: params.get(key) ?? "",
    onChange: (event: { target: { value: string } }) => onChange(key, event.target.value),
  });
  return (
    <section aria-label="Audit filters" className="audit-filters">
      <SearchInput
        label="Search reasons"
        value={params.get("q") ?? ""}
        resultCount={resultCount}
        placeholder="Words in the stated reason"
        onSearch={(value) => onChange("q", value)}
      />
      <DateInput label="From date" {...pick("start")} />
      <DateInput label="To date" {...pick("end")} />
      <Select
        label="Done by"
        placeholder="Anyone"
        options={choices}
        disabled={!people}
        {...pick("actor_id")}
      />
      <Select
        label="About person"
        placeholder="Anyone"
        options={choices}
        disabled={!people}
        {...pick("person_id")}
      />
      <Select
        label="Unit"
        placeholder={units ? "All units" : "Loading units…"}
        options={units ?? []}
        disabled={!units}
        {...pick("unit_id")}
      />
      <Select label="Kind of change" placeholder="All kinds" options={GROUP_OPTIONS} {...pick("group")} />
      <Select label="Outcome" placeholder="Any outcome" options={OUTCOME_OPTIONS} {...pick("outcome")} />
      <div className="audit-actions">
        <Button variant="quiet" onClick={onReset}>
          Clear audit filters
        </Button>
      </div>
      {lookupError && <ErrorState message={lookupError} onRetry={onRetryLookups} />}
    </section>
  );
}
