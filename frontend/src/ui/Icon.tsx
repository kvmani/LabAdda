import { ICONS, type IconName } from "./icons";
import "./icon.css";

type IconProps = {
  name: IconName;
  /** Accessible text. Leave it out when the icon sits next to a word that says the same thing. */
  label?: string;
  size?: "sm" | "md" | "lg";
};

/** A local SVG icon drawn in the current text colour. Decorative unless it has a label. */
export function Icon({ name, label, size = "md" }: IconProps) {
  const labelled = label !== undefined;
  return (
    <svg
      className={`ui-icon ui-icon--${size}`}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={labelled ? "img" : undefined}
      aria-label={label}
      aria-hidden={labelled ? undefined : true}
      focusable="false"
    >
      <path d={ICONS[name]} />
    </svg>
  );
}
