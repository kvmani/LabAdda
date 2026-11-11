import { Link } from "react-router-dom";
import { Icon } from "./Icon";
import "./navigation.css";

export type Crumb = { label: string; to?: string };

/** The path to the current page. The last item is the current page and is not a link. */
export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="ui-breadcrumbs">
      <ol>
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${index}-${item.label}`}>
              {last || !item.to ? (
                <span aria-current={last ? "page" : undefined}>{item.label}</span>
              ) : (
                <Link to={item.to}>{item.label}</Link>
              )}
              {!last && <Icon name="chevron-right" size="sm" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
