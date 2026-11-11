import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Icon } from "./Icon";
import type { IconName } from "./icons";
import "./overlay.css";

export type MenuItem = {
  label: string;
  onSelect: () => void;
  icon?: IconName;
  danger?: boolean;
  disabled?: boolean;
};

type MenuProps = {
  /** Accessible name of the button and the menu. */
  label: string;
  /**
   * Shorter text to show on the button instead of `label`. It must appear inside `label`
   * (WCAG 2.5.3), for example label "Account menu for Asha Rao" and visibleLabel "Asha Rao".
   */
  visibleLabel?: string;
  items: MenuItem[];
  icon?: IconName;
};

/**
 * A button that opens a list of actions (WAI-ARIA menu button). Arrow keys, Home and End move
 * between items, Enter or Space chooses one, and Escape or Tab closes the menu.
 */
export function Menu({ label, visibleLabel, items, icon = "chevron-down" }: MenuProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const id = useId();
  const enabled = items.map((item, index) => (item.disabled ? -1 : index)).filter((index) => index >= 0);

  useEffect(() => {
    if (!open) return undefined;
    list.current?.querySelectorAll<HTMLElement>("[role='menuitem']")[active]?.focus();
    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node;
      if (!list.current?.contains(target) && !trigger.current?.contains(target)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, active]);

  function openAt(index: number) {
    setActive(index);
    setOpen(true);
  }

  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) trigger.current?.focus();
  }

  function move(step: number) {
    const position = enabled.indexOf(active);
    const next = enabled[(position + step + enabled.length) % enabled.length];
    if (next !== undefined) setActive(next);
  }

  function onListKeyDown(event: KeyboardEvent) {
    const actions: Record<string, () => void> = {
      ArrowDown: () => move(1),
      ArrowUp: () => move(-1),
      Home: () => setActive(enabled[0] ?? 0),
      End: () => setActive(enabled[enabled.length - 1] ?? 0),
      Escape: () => close(true),
    };
    if (event.key === "Tab") {
      close(false);
      return;
    }
    const action = actions[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  }

  function choose(item: MenuItem) {
    close(true);
    item.onSelect();
  }

  return (
    <div className="ui-menu">
      <button
        ref={trigger}
        type="button"
        className="ui-button ui-button--secondary ui-button--md"
        aria-haspopup="menu"
        aria-label={visibleLabel ? label : undefined}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => (open ? close(false) : openAt(enabled[0] ?? 0))}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            openAt(enabled[0] ?? 0);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            openAt(enabled[enabled.length - 1] ?? 0);
          }
        }}
      >
        <span>{visibleLabel ?? label}</span>
        <Icon name={icon} size="sm" />
      </button>
      {open && (
        <ul
          ref={list}
          id={id}
          className="ui-menu__list"
          role="menu"
          aria-label={label}
          onKeyDown={onListKeyDown}
        >
          {items.map((item, index) => (
            <li
              key={item.label}
              role="menuitem"
              tabIndex={index === active ? 0 : -1}
              aria-disabled={item.disabled || undefined}
              className={item.danger ? "ui-menu__item ui-menu__item--danger" : "ui-menu__item"}
              onClick={() => !item.disabled && choose(item)}
              onKeyDown={(event) => {
                if ((event.key === "Enter" || event.key === " ") && !item.disabled) {
                  event.preventDefault();
                  choose(item);
                }
              }}
            >
              {item.icon && <Icon name={item.icon} size="sm" />}
              <span>{item.label}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
