import { useId } from "react";
import "./field.css";

type SwitchProps = {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  hint?: string;
};

/** An on/off setting that takes effect at once. Shows "On" or "Off" as text, not only colour. */
export function Switch({ label, checked, onChange, disabled, hint }: SwitchProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="ui-switch-row">
      <span className="ui-switch__label" id={`${id}-label`}>
        {label}
        {hint && (
          <span className="ui-field__hint" id={hintId}>
            {hint}
          </span>
        )}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={hintId}
        disabled={disabled}
        className="ui-switch"
        onClick={() => onChange(!checked)}
      >
        <span className="ui-switch__track" aria-hidden="true">
          <span className="ui-switch__thumb" />
        </span>
        <span className="ui-switch__state">{checked ? "On" : "Off"}</span>
      </button>
    </div>
  );
}
