import type { ButtonHTMLAttributes, ReactNode } from "react";
import { classNames } from "./classNames";
import { Icon } from "./Icon";
import type { IconName } from "./icons";
import "./button.css";

export type ButtonVariant = "primary" | "secondary" | "quiet" | "danger";

type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  icon?: IconName;
  /** While true the button is disabled and shows `busyLabel`, so a save cannot be sent twice. */
  busy?: boolean;
  busyLabel?: string;
  children: ReactNode;
};

/** A labelled action. Name the action and its object: "Transfer Asha Rao", not "Submit". */
export function Button({
  variant = "secondary",
  size = "md",
  icon,
  busy = false,
  busyLabel = "Working…",
  type = "button",
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      className={classNames("ui-button", `ui-button--${variant}`, `ui-button--${size}`)}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
    >
      {icon && !busy && <Icon name={icon} size={size === "sm" ? "sm" : "md"} />}
      <span>{busy ? busyLabel : children}</span>
    </button>
  );
}
