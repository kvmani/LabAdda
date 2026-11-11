import {
  cloneElement,
  useId,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type MouseEvent,
  type ReactElement,
} from "react";
import "./overlay.css";

type TriggerProps = {
  "aria-describedby"?: string;
  onMouseEnter?: (event: MouseEvent<HTMLElement>) => void;
  onMouseLeave?: (event: MouseEvent<HTMLElement>) => void;
  onFocus?: (event: FocusEvent<HTMLElement>) => void;
  onBlur?: (event: FocusEvent<HTMLElement>) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLElement>) => void;
};

type TooltipProps = {
  /** A short explanation of an unfamiliar term or control (UX-08). Never essential information. */
  text: string;
  /** One focusable element, such as a button or link. Its own handlers keep working. */
  children: ReactElement<TriggerProps>;
};

/** Shows `text` on hover and keyboard focus of its trigger; Escape hides it (WCAG 1.4.13). */
export function Tooltip({ text, children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  const own = children.props;
  const trigger = cloneElement(children, {
    "aria-describedby": id,
    onMouseEnter: (event: MouseEvent<HTMLElement>) => {
      own.onMouseEnter?.(event);
      setVisible(true);
    },
    onMouseLeave: (event: MouseEvent<HTMLElement>) => {
      own.onMouseLeave?.(event);
      setVisible(false);
    },
    onFocus: (event: FocusEvent<HTMLElement>) => {
      own.onFocus?.(event);
      setVisible(true);
    },
    onBlur: (event: FocusEvent<HTMLElement>) => {
      own.onBlur?.(event);
      setVisible(false);
    },
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      own.onKeyDown?.(event);
      if (event.key === "Escape") setVisible(false);
    },
  });
  return (
    <span className="ui-tooltip">
      {trigger}
      <span id={id} role="tooltip" className="ui-tooltip__bubble" hidden={!visible}>
        {text}
      </span>
    </span>
  );
}
