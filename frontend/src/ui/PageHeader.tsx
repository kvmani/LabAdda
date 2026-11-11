import type { ReactNode } from "react";
import { Icon } from "./Icon";
import "./display.css";

type PageHeaderProps = {
  title: string;
  /** One line saying what this page covers and who can see it. */
  scope?: ReactNode;
  /** The page's main action, usually one primary Button. */
  action?: ReactNode;
  /** Link to this page's help topic (UX-08). */
  helpHref?: string;
};

/** The heading block at the top of every page: title, scope, main action and help. */
export function PageHeader({ title, scope, action, helpHref }: PageHeaderProps) {
  return (
    <header className="ui-page-header">
      <div className="ui-page-header__text">
        <h1 className="ui-page-header__title">{title}</h1>
        {scope && <p className="ui-page-header__scope">{scope}</p>}
      </div>
      <div className="ui-page-header__actions">
        {helpHref && (
          <a className="ui-page-header__help" href={helpHref}>
            <Icon name="help" size="sm" />
            <span>Help with this page</span>
          </a>
        )}
        {action}
      </div>
    </header>
  );
}
