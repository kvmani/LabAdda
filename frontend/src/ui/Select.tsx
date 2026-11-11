import type { SelectHTMLAttributes } from "react";
import { Field } from "./Field";

export type SelectOption = { value: string; label: string; disabled?: boolean };

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id" | "className" | "children"> & {
  label: string;
  options: SelectOption[];
  /** Text of an empty first option, for a choice that is not yet made. */
  placeholder?: string;
  hint?: string;
  error?: string | null;
};

/** A labelled native drop-down list. */
export function Select({ label, options, placeholder, hint, error, required, ...select }: SelectProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(control) => (
        <select {...select} {...control} className="ui-input ui-select">
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}
