import { useState } from "react";
import { Button, SearchInput } from "../../ui";
import { usePeopleData } from "../people/usePeopleData";
import type { Directory } from "../people/types";
import { matchUnits } from "./layout";
import type { OrgUnit } from "./types";

/** Find a unit by name or code, or a person by name, and reveal their unit in the chart. */
export function OrgSearch({
  units,
  onReveal,
  onDenied,
}: {
  units: OrgUnit[];
  onReveal: (unitId: string) => void;
  onDenied: () => void;
}) {
  const [query, setQuery] = useState("");
  const found = matchUnits(units, query).slice(0, 8);
  const people = usePeopleData<Directory>(
    query.length >= 2 ? `/admin/people?q=${encodeURIComponent(query)}&limit=8` : null,
    onDenied,
  );
  const placed = (people.data?.people ?? []).filter((person) => person.home_unit);
  const total = query ? found.length + placed.length : null;
  return (
    <div className="org-search">
      <SearchInput label="Find a unit or person" onSearch={setQuery} resultCount={total} />
      {query && (
        <ul className="org-search__results" aria-label="Search results">
          {found.map((unit) => (
            <li key={unit.id}>
              <Button variant="quiet" onClick={() => onReveal(unit.id)}>{`Show ${unit.name}`}</Button>
            </li>
          ))}
          {placed.map((person) => (
            <li key={person.id}>
              <Button variant="quiet" onClick={() => person.home_unit && onReveal(person.home_unit.id)}>
                {`Show ${person.display_name} in ${person.home_unit?.name ?? ""}`}
              </Button>
            </li>
          ))}
          {total === 0 && !people.loading && <li>No unit or person matches.</li>}
        </ul>
      )}
    </div>
  );
}
