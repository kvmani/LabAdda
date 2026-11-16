import { Button } from "../../ui";

type Props = {
  label: string;
  canEditText: boolean;
  onEdit: () => void;
  onMove: (dx: number, dy: number) => void;
  onErase: () => void;
};
export function SelectedObjectControls({ label, canEditText, onEdit, onMove, onErase }: Props) {
  return (
    <section aria-label="Selected board item">
      <p role="status">Selected: {label}. Drag to move, or use the buttons below.</p>
      {canEditText && <Button onClick={onEdit}>Edit selected item</Button>}
      <Button onClick={() => onMove(-10, 0)}>Move left</Button>
      <Button onClick={() => onMove(10, 0)}>Move right</Button>
      <Button onClick={() => onMove(0, -10)}>Move up</Button>
      <Button onClick={() => onMove(0, 10)}>Move down</Button>
      <Button onClick={onErase}>Erase selected item</Button>
    </section>
  );
}
