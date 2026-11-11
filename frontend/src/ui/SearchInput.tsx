import { useEffect, useId, useRef, useState } from "react";
import { IconButton } from "./IconButton";
import { Icon } from "./Icon";
import "./base.css";
import "./field.css";

type SearchInputProps = {
  label: string;
  /** Called with the trimmed text after typing pauses for `delay` milliseconds, and on clear. */
  onSearch: (query: string) => void;
  initialValue?: string;
  placeholder?: string;
  /** Number of results for the current query; announced to screen readers when it changes. */
  resultCount?: number | null;
  delay?: number;
};

/** A search box that waits for typing to pause before searching, with a clear button. */
export function SearchInput({
  label,
  onSearch,
  initialValue = "",
  placeholder,
  resultCount = null,
  delay = 300,
}: SearchInputProps) {
  const id = useId();
  const [value, setValue] = useState(initialValue);
  const onSearchRef = useRef(onSearch);
  onSearchRef.current = onSearch;
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return undefined;
    }
    const timer = window.setTimeout(() => onSearchRef.current(value.trim()), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  function clear() {
    setValue("");
    onSearchRef.current("");
  }

  return (
    <div className="ui-search">
      <label htmlFor={id} className="ui-visually-hidden">
        {label}
      </label>
      <span className="ui-search__icon">
        <Icon name="search" size="sm" />
      </span>
      <input
        id={id}
        type="search"
        className="ui-input ui-search__input"
        value={value}
        placeholder={placeholder}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && value) clear();
        }}
      />
      {value && <IconButton icon="close" label={`Clear ${label.toLowerCase()}`} size="sm" onClick={clear} />}
      <span className="ui-visually-hidden" role="status" aria-live="polite">
        {resultCount === null ? "" : `${resultCount} ${resultCount === 1 ? "result" : "results"}`}
      </span>
    </div>
  );
}
