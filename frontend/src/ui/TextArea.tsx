import type { TextareaHTMLAttributes } from "react";
import { Field } from "./Field";

type TextAreaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id" | "className"> & {
  label: string;
  hint?: string;
  error?: string | null;
};

/** A labelled multi-line text field. */
export function TextArea({ label, hint, error, required, rows = 4, ...textarea }: TextAreaProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(control) => <textarea {...textarea} {...control} rows={rows} className="ui-input ui-textarea" />}
    </Field>
  );
}
