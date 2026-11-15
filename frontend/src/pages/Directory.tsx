import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Button, Card, EmptyState, PageHeader, Skeleton, TextInput } from "../ui";
import type { Person } from "../features/people/types";
import "./directory.css";

export function Directory() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [designation, setDesignation] = useState("");
  const [sort, setSort] = useState<"name" | "username" | "employee_no">("name");
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");

    const params: Record<string, string | number> = {
      q: query.trim(),
      specialization: specialization.trim(),
      designation: designation.trim(),
      sort,
      limit: 100,
    };

    const timer = setTimeout(() => {
      api<{ people: Person[]; next_cursor: string | null }>("/people/directory", { params })
        .then((res) => {
          if (active) {
            setPeople(res.people);
          }
        })
        .catch((err: unknown) => {
          if (active) {
            setError(errorMessage(err));
          }
        })
        .finally(() => {
          if (active) {
            setLoading(false);
          }
        });
    }, 150);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, specialization, designation, sort]);

  function clearFilters() {
    setQuery("");
    setSpecialization("");
    setDesignation("");
    setSort("name");
  }

  return (
    <div className="directory-page">
      <PageHeader
        title="Staff Directory"
        scope="Search and locate colleagues by name, designation, specialization, extension, mobile, or unit."
      />

      <div className="directory-search-card">
        <Card>
          <div className="directory-search-bar">
            <input
              className="ui-input directory-search-input"
              type="search"
              placeholder="Search staff by name, username, designation, keywords, phone, mobile, email…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search staff directory"
            />
            {query && (
              <Button variant="quiet" onClick={() => setQuery("")}>
                ✕ Clear
              </Button>
            )}
          </div>

          <div className="directory-advanced-toggle">
            <Button
              variant="quiet"
              size="sm"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? "▲ Hide advanced search" : "▼ Advanced search options"}
            </Button>
          </div>

          {showAdvanced && (
            <div className="directory-filters-grid">
              <TextInput
                label="Field of Specialization"
                placeholder="e.g. Thin Films, Propulsion, AI"
                value={specialization}
                onChange={(e) => setSpecialization(e.target.value)}
              />
              <TextInput
                label="Designation"
                placeholder="e.g. Scientist, Technical Officer"
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Sort by</label>
                <select
                  className="ui-input"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as "name" | "username" | "employee_no")}
                >
                  <option value="name">Name</option>
                  <option value="username">Username</option>
                  <option value="employee_no">Employee Number</option>
                </select>
              </div>
              <div style={{ display: "flex", alignItems: "flex-end" }}>
                <Button variant="secondary" size="sm" onClick={clearFilters}>
                  Reset all filters
                </Button>
              </div>
            </div>
          )}

          <p className="directory-count">
            {loading ? "Searching staff directory…" : `Found ${people.length} ${people.length === 1 ? "colleague" : "colleagues"}`}
          </p>
        </Card>
      </div>

      {error && (
        <p className="chat__error" role="alert">
          {error}
        </p>
      )}

      {loading && people.length === 0 ? (
        <Skeleton label="Loading staff directory…" lines={6} />
      ) : people.length === 0 ? (
        <EmptyState title="No staff members matched your search.">
          Try broader keywords or reset your search filters.
        </EmptyState>
      ) : (
        <div className="directory-grid">
          {people.map((person) => {
            const specKeywords = person.specialization
              ? person.specialization
                  .split(/[,;]+/)
                  .map((s) => s.trim())
                  .filter(Boolean)
              : [];

            return (
              <div key={person.id} className="directory-card">
                <div className="directory-card__top">
                  {person.avatar_data ? (
                    <img
                      src={person.avatar_data}
                      alt={person.display_name || person.username}
                      className="directory-card__avatar"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : (
                    <div className="directory-card__avatar">
                      {(person.display_name || person.username || "??").slice(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div className="directory-card__info">
                    <div className="directory-card__name" title={person.display_name}>
                      {person.display_name}
                    </div>
                    <div className="directory-card__username">@{person.username}</div>
                    {person.designation && (
                      <div className="directory-card__designation">{person.designation}</div>
                    )}
                    {person.home_unit && (
                      <div className="directory-card__unit">🏛️ {person.home_unit.name}</div>
                    )}
                  </div>
                </div>

                {specKeywords.length > 0 && (
                  <div className="directory-card__specialization">
                    {specKeywords.map((kw, i) => (
                      <span key={i} className="directory-card__spec-tag">
                        {kw}
                      </span>
                    ))}
                  </div>
                )}

                <div className="directory-card__contacts">
                  {(person.contact_phone || person.extension) && (
                    <div className="directory-card__contact-item" title="Office Extension">
                      <span>📞</span>
                      <span>Ext: {person.contact_phone ?? person.extension}</span>
                    </div>
                  )}
                  {person.mobile && (
                    <div className="directory-card__contact-item" title="Mobile Number">
                      <span>📱</span>
                      <span>Mob: {person.mobile}</span>
                    </div>
                  )}
                  {person.contact_email && (
                    <div className="directory-card__contact-item" title="Work Email">
                      <span>✉️</span>
                      <a href={`mailto:${person.contact_email}`}>{person.contact_email}</a>
                    </div>
                  )}
                  {person.alternate_email && (
                    <div className="directory-card__contact-item" title="Alternate Email">
                      <span>📧</span>
                      <a href={`mailto:${person.alternate_email}`}>{person.alternate_email}</a>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
