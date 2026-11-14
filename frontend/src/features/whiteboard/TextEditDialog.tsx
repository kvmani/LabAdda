import { useState, useEffect } from "react";
import { Button, Dialog, TextArea } from "../../ui";
import { PEN_COLORS } from "./types";

type Props = {
  open: boolean;
  initialText?: string;
  initialColor?: string;
  authorInfo?: { name: string; time: string };
  onClose: () => void;
  onSave: (text: string, color: string) => void;
  onDelete?: () => void;
};

export function TextEditDialog({
  open,
  initialText = "",
  initialColor = "#1f2933",
  authorInfo,
  onClose,
  onSave,
  onDelete,
}: Props) {
  const [text, setText] = useState(initialText);
  const [color, setColor] = useState(initialColor);

  useEffect(() => {
    if (open) {
      setText(initialText);
      setColor(initialColor);
    }
  }, [open, initialText, initialColor]);

  function handleSave() {
    if (!text.trim()) return;
    onSave(text.trim().slice(0, 1000), color);
    onClose();
  }

  return (
    <Dialog
      open={open}
      title={initialText ? "Edit text label" : "Add text label"}
      onClose={onClose}
      size="sm"
      footer={
        <div
          style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}
        >
          {onDelete ? (
            <Button variant="danger" onClick={onDelete}>
              Erase
            </Button>
          ) : (
            <div />
          )}
          <div style={{ display: "flex", gap: "8px" }}>
            <Button variant="quiet" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={!text.trim()}>
              Save text
            </Button>
          </div>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {authorInfo && (
          <div
            style={{
              padding: "8px 12px",
              background: "var(--color-bg-secondary, #f0f4f8)",
              borderRadius: "6px",
              fontSize: "13px",
              color: "var(--color-text-secondary, #627d98)",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>
              Added by <strong>{authorInfo.name}</strong>
            </span>
            <span>{authorInfo.time}</span>
          </div>
        )}

        <TextArea
          label="Text content"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={1000}
          rows={3}
        />

        <div>
          <span style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
            Text color
          </span>
          <div
            style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}
            role="radiogroup"
            aria-label="Text colour"
          >
            {PEN_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={color === c}
                aria-label={`Color ${c}`}
                onClick={() => setColor(c)}
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  background: c,
                  border: color === c ? "3px solid #1565c0" : "1px solid #9aa5b1",
                  boxShadow: color === c ? "0 0 0 2px white inset" : "none",
                  cursor: "pointer",
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </Dialog>
  );
}
