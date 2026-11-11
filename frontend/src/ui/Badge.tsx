import "./base.css";
import "./display.css";

type BadgeProps = {
  count: number;
  /** What is being counted, read with the number: "3 unread messages". */
  label: string;
  /** Show "99+" above this value; the full number is still announced. */
  max?: number;
};

/** A small count, such as unread items. Renders nothing for zero. */
export function Badge({ count, label, max = 99 }: BadgeProps) {
  if (count <= 0) return null;
  return (
    <span className="ui-badge">
      <span aria-hidden="true">{count > max ? `${max}+` : count}</span>
      <span className="ui-visually-hidden">{`${count} ${label}`}</span>
    </span>
  );
}
