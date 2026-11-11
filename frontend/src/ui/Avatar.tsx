import "./display.css";

const TONES = ["info", "ok", "warn", "neutral", "danger"] as const;

/** Up to two initials from a display name. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const first = words[0]?.[0] ?? "?";
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

/** A stable tone for a user ID, so the same person always has the same colour. */
export function toneFor(id: string): (typeof TONES)[number] {
  let hash = 0;
  for (const character of id) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return TONES[hash % TONES.length] ?? "neutral";
}

/** Initials in a circle. Decorative: the person's name is always written beside it. */
export function Avatar({ id, name, size = "md" }: { id: string; name: string; size?: "sm" | "md" }) {
  return (
    <span className={`ui-avatar ui-avatar--${size} ui-tag--${toneFor(id)}`} aria-hidden="true" title={name}>
      {initials(name)}
    </span>
  );
}
