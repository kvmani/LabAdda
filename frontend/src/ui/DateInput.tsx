import type { InputHTMLAttributes } from "react";
import { Field } from "./Field";

type DateInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className" | "type"> & {
  label: string;
  hint?: string;
  error?: string | null;
  /** "date" for a calendar day; "datetime-local" for a day and time in the site time zone. */
  kind?: "date" | "datetime-local";
};

/** A labelled date (or date and time) field using the browser's own picker. */
export function DateInput({ label, hint, error, required, kind = "date", ...input }: DateInputProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(control) => <input {...input} {...control} type={kind} className="ui-input" />}
    </Field>
  );
}
