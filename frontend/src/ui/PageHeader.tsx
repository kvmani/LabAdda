import { useContext, type ReactNode } from "react";
import { HelpEntryContext } from "./helpEntry";
import { Icon } from "./Icon";
import "./display.css";

type PageHeaderProps = {
  title: string;
  /** One line saying what this page covers and who can see it. */
  scope?: ReactNode;
  /** The page's main action, usually one primary Button. */
  action?: ReactNode;
  /** Plain link used when the help centre has no page for the current screen (UX-08). */
  helpHref?: string;
};

/** The heading block at the top of every page: title, scope, main action and help. */
export function PageHeader({ title, scope, action, helpHref }: PageHeaderProps) {
  const HelpEntry = useContext(HelpEntryContext);
  const fallback = helpHref ? (
    <a className="ui-page-header__help" href={helpHref}>
      <Icon name="help" size="sm" />
      <span>Help with this page</span>
    </a>
  ) : null;
  return (
    <header className="ui-page-header">
      <div className="ui-page-header__text">
        <h1 className="ui-page-header__title">{title}</h1>
        {scope && <p className="ui-page-header__scope">{scope}</p>}
      </div>
      <div className="ui-page-header__actions">
        {HelpEntry ? <HelpEntry fallback={fallback} /> : fallback}
        {action}
      </div>
    </header>
  );
}
