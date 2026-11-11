import { useId, type InputHTMLAttributes } from "react";
import "./field.css";

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className" | "type"> & {
  label: string;
  hint?: string;
};

/** A labelled check box; the label is clickable. */
export function Checkbox({ label, hint, ...input }: CheckboxProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="ui-check">
      <input {...input} id={id} type="checkbox" className="ui-check__box" aria-describedby={hintId} />
      <label htmlFor={id} className="ui-check__label">
        {label}
        {hint && (
          <span className="ui-field__hint" id={hintId}>
            {hint}
          </span>
        )}
      </label>
    </div>
  );
}
