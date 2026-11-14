import { useState, useEffect } from "react";
import { Button, Dialog, TextArea } from "../../ui";
import { STICKY_SHAPES, STICKY_SIZES } from "./shapes";
import { STICKY_COLORS, type StickyConfig, type StickyShape, type StickySize } from "./types";

type Props = {
  open: boolean;
  title?: string;
  initialConfig: StickyConfig;
  authorInfo?: { name: string; time: string };
  onClose: () => void;
  onSave: (config: StickyConfig) => void;
  onDelete?: () => void;
};

export function StickyEditDialog({
  open,
  title = "Edit sticky note",
  initialConfig,
  authorInfo,
  onClose,
  onSave,
  onDelete,
}: Props) {
  const [text, setText] = useState(initialConfig.text);
  const [shape, setShape] = useState<StickyShape>(initialConfig.shape);
  const [size, setSize] = useState<StickySize>(initialConfig.size);
  const [color, setColor] = useState(initialConfig.color);

  useEffect(() => {
    if (open) {
      setText(initialConfig.text);
      setShape(initialConfig.shape);
      setSize(initialConfig.size);
      setColor(initialConfig.color);
    }
  }, [open, initialConfig]);

  function handleSave() {
    if (!text.trim()) return;
    onSave({ text: text.trim().slice(0, 1000), shape, size, color });
    onClose();
  }

  return (
    <Dialog
      open={open}
      title={title}
      onClose={onClose}
      size="md"
      footer={
        <div
          style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}
        >
          {onDelete ? (
            <Button variant="danger" onClick={onDelete}>
              Erase note
            </Button>
          ) : (
            <div />
          )}
          <div style={{ display: "flex", gap: "8px" }}>
            <Button variant="quiet" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={!text.trim()}>
              Save note
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
          label="Note text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={1000}
          rows={4}
        />

        <div>
          <span style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
            Note shape
          </span>
          <div
            style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}
            role="radiogroup"
            aria-label="Sticky note shape"
          >
            {STICKY_SHAPES.map((s) => (
              <button
                key={s.id}
                type="button"
                role="radio"
                aria-checked={shape === s.id}
                onClick={() => setShape(s.id)}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  border: shape === s.id ? "2px solid var(--color-primary, #1565c0)" : "1px solid #d2d6dc",
                  background: shape === s.id ? "#e8f0fe" : "white",
                  cursor: "pointer",
                  fontWeight: shape === s.id ? 600 : 400,
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <span>{s.icon}</span>
                <span>{s.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <span style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
            Note size
          </span>
          <div style={{ display: "flex", gap: "8px" }} role="radiogroup" aria-label="Sticky note size">
            {STICKY_SIZES.map((sz) => (
              <button
                key={sz.id}
                type="button"
                role="radio"
                aria-checked={size === sz.id}
                onClick={() => setSize(sz.id)}
                style={{
                  padding: "6px 16px",
                  borderRadius: "6px",
                  border: size === sz.id ? "2px solid var(--color-primary, #1565c0)" : "1px solid #d2d6dc",
                  background: size === sz.id ? "#e8f0fe" : "white",
                  cursor: "pointer",
                  fontWeight: size === sz.id ? 600 : 400,
                  fontSize: "13px",
                }}
              >
                {sz.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <span style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
            Pastel color
          </span>
          <div style={{ display: "flex", gap: "10px" }} role="radiogroup" aria-label="Sticky note colour">
            {STICKY_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={color === c}
                aria-label={`Color ${c}`}
                onClick={() => setColor(c)}
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  background: c,
                  border: color === c ? "3px solid #1f2933" : "1px solid #9aa5b1",
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
