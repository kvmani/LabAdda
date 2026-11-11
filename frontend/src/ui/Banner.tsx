import type { ReactNode } from "react";
import { Icon } from "./Icon";
import "./display.css";

type BannerProps = {
  /** "warning" is for notices people must plan around, such as planned downtime. */
  level?: "info" | "warning";
  children: ReactNode;
};

/** A full-width site notice. Text is rendered as text, so markup typed by an author is shown as typed. */
export function Banner({ level = "info", children }: BannerProps) {
  return (
    <div className={`ui-banner ui-banner--${level}`} role="status">
      <Icon name={level === "warning" ? "warning" : "info"} />
      <p className="ui-banner__text">
        <span className="ui-visually-hidden">{level === "warning" ? "Warning: " : "Notice: "}</span>
        {children}
      </p>
    </div>
  );
}
