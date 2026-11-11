import { useId, type ReactNode } from "react";
import "./field.css";

/** Props a field passes to its control so the label, hint and error are announced with it. */
export type ControlProps = {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  required?: boolean;
};

type FieldProps = {
  label: string;
  hint?: string;
  /** Shown under the control and announced; marks the control invalid. */
  error?: string | null;
  required?: boolean;
  /** Hide the label visually but keep it for screen readers (search boxes in a toolbar). */
  hideLabel?: boolean;
  children: (control: ControlProps) => ReactNode;
};

/** Label, optional hint and error around one form control (UX-02). */
export function Field({ label, hint, error, required, hideLabel = false, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="ui-field">
      <label className={hideLabel ? "ui-visually-hidden" : "ui-field__label"} htmlFor={id}>
        {label}
        {required && " "}
        {required && <span className="ui-field__required">(required)</span>}
      </label>
      {hint && (
        <p className="ui-field__hint" id={hintId}>
          {hint}
        </p>
      )}
      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
        required,
      })}
      {error && (
        <p className="ui-field__error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
