import { Link } from "react-router-dom";
import { EmptyState, PageHeader } from "../ui";

/** Placeholder for the in-app help centre until package H1 delivers it (HP-01). */
export function Help() {
  return (
    <section>
      <PageHeader
        title="Help"
        scope="Guides for members, stewards, administrators and the server operator."
      />
      <EmptyState title="The help centre is being written">
        Step-by-step guides for every screen will appear here. Until then, ask a steward of your workspace or
        your LabAdda administrator. <Link to="/">Go to your home workspace</Link>.
      </EmptyState>
    </section>
  );
}
