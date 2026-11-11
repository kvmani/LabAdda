import type { ButtonHTMLAttributes } from "react";
import { classNames } from "./classNames";
import { Icon } from "./Icon";
import type { IconName } from "./icons";
import "./button.css";

type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children" | "title"> & {
  icon: IconName;
  /** Required: becomes the accessible name and the hover hint. */
  label: string;
  size?: "md" | "sm";
  variant?: "quiet" | "secondary";
};

/** A button that shows only an icon. Its label is announced and shown on hover. */
export function IconButton({
  icon,
  label,
  size = "md",
  variant = "quiet",
  type = "button",
  ...rest
}: IconButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      aria-label={label}
      title={label}
      className={classNames("ui-button", "ui-icon-button", `ui-button--${variant}`, `ui-button--${size}`)}
    >
      <Icon name={icon} size={size === "sm" ? "sm" : "md"} />
    </button>
  );
}
