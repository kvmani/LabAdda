import { DateInput, Select } from "../../ui";

type Props = {
  later: boolean;
  day: string;
  onLater: (later: boolean) => void;
  onDay: (day: string) => void;
};

/** Now, or the start of a later day in the site's time zone (PO-06). */
export function WhenControl({ later, day, onLater, onDay }: Props) {
  return (
    <div className="people-change__when">
      <Select
        label="When should this happen?"
        value={later ? "later" : "now"}
        onChange={(event) => onLater(event.target.value === "later")}
        options={[
          { value: "now", label: "Now" },
          { value: "later", label: "At the start of a later day" },
        ]}
        hint={
          later
            ? "Nothing changes until that day. It is checked again then and applied only if still valid."
            : undefined
        }
      />
      {later && (
        <DateInput label="Day it takes effect" required value={day} onChange={(e) => onDay(e.target.value)} />
      )}
    </div>
  );
}
