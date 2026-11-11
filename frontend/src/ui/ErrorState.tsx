import { Button } from "./Button";
import { Icon } from "./Icon";
import "./display.css";

type ErrorStateProps = {
  /** What failed and what to do next, in plain words. */
  message: string;
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
};

/** A failed load: says what happened and offers a retry when one can help (UX-04). */
export function ErrorState({
  message,
  title = "This could not be loaded",
  onRetry,
  retryLabel = "Try again",
}: ErrorStateProps) {
  return (
    <div className="ui-state ui-state--error" role="alert">
      <p className="ui-state__title">
        <Icon name="error" />
        <span>{title}</span>
      </p>
      <p className="ui-state__body">{message}</p>
      {onRetry && (
        <div className="ui-state__action">
          <Button icon="refresh" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      )}
    </div>
  );
}
