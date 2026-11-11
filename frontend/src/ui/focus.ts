import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/** Elements inside `container` that Tab can reach, in document order. */
export function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (element) => !element.closest("[hidden],[inert]"),
  );
}

/**
 * Keep keyboard focus inside a modal surface while it is open.
 *
 * On open, focus moves to the element marked `data-autofocus`, else the first focusable element,
 * else the container. Tab and Shift+Tab wrap inside it and Escape calls `onEscape`. On close,
 * focus returns to the element that had it before, so keyboard users keep their place.
 */
export function useFocusTrap(
  container: RefObject<HTMLElement | null>,
  active: boolean,
  onEscape: () => void,
): void {
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    const element = container.current;
    if (!active || !element) return undefined;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const preferred = element.querySelector<HTMLElement>("[data-autofocus]");
    (preferred ?? focusableWithin(element)[0] ?? element).focus();

    function onKeyDown(event: KeyboardEvent) {
      if (!element) return;
      if (event.key === "Escape") {
        event.stopPropagation();
        onEscapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusableWithin(element);
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) {
        event.preventDefault();
        return;
      }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === element)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    element.addEventListener("keydown", onKeyDown);
    return () => {
      element.removeEventListener("keydown", onKeyDown);
      if (previous?.isConnected) previous.focus();
    };
  }, [active, container]);
}
