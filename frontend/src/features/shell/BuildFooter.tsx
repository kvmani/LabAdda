import { BUILD_LINE, CREDIT } from "../../buildInfo";
import "./build-footer.css";

/** Two quiet lines naming the software, its build and its author; shown on every page. */
export function BuildFooter({ tone = "page" }: { tone?: "page" | "inverse" }) {
  return (
    <footer className={`build-footer build-footer--${tone}`} data-testid="build-footer">
      <p data-testid="build-line">{BUILD_LINE}</p>
      <p data-testid="build-credit">{CREDIT}</p>
    </footer>
  );
}
