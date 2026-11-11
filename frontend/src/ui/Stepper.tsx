import { Icon } from "./Icon";
import "./base.css";
import "./navigation.css";

type StepperProps = {
  steps: string[];
  /** Index of the step being shown, starting at 0. */
  current: number;
};

/** Progress through a multi-step change such as a transfer: which step, and how many remain. */
export function Stepper({ steps, current }: StepperProps) {
  return (
    <div className="ui-stepper">
      <p className="ui-stepper__summary">
        Step {current + 1} of {steps.length}: {steps[current]}
      </p>
      <ol className="ui-stepper__list">
        {steps.map((step, index) => {
          const state = index < current ? "done" : index === current ? "current" : "todo";
          return (
            <li
              key={step}
              className={`ui-stepper__step ui-stepper__step--${state}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="ui-stepper__marker" aria-hidden="true">
                {state === "done" ? <Icon name="check" size="sm" /> : index + 1}
              </span>
              <span>
                {step}
                {state === "done" && <span className="ui-visually-hidden"> (done)</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
