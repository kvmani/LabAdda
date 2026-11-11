import type { InputHTMLAttributes } from "react";
import { Field } from "./Field";

type TextInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className" | "type"> & {
  label: string;
  hint?: string;
  error?: string | null;
  type?: "text" | "email" | "password" | "number" | "tel";
};

/** A labelled single-line text field. */
export function TextInput({ label, hint, error, required, type = "text", ...input }: TextInputProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(control) => <input {...input} {...control} type={type} className="ui-input" />}
    </Field>
  );
}
