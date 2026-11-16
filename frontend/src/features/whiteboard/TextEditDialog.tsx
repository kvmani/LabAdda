import styles from "./TextEditors.module.css";
import { TextStyleFields } from "./TextStyleFields";
import { type TextStyle } from "./textStyle";
import { useState, useEffect } from "react";
import { Button, Dialog, TextArea } from "../../ui";
import { PEN_COLORS } from "./types";

type Props = {
  open: boolean;
  canEdit?: boolean;
  initialText?: string;
  initialColor?: string;
  initialStyle?: Partial<TextStyle>;
  authorInfo?: { name: string; time: string };
  onClose: () => void;
  onSave: (text: string, color: string, style: TextStyle) => void;
  onDelete?: () => void;
};

export function TextEditDialog({
  open,
  canEdit = true,
  initialText = "",
  initialColor = "#1f2933",
  initialStyle,
  authorInfo,
  onClose,
  onSave,
  onDelete,
}: Props) {
  const [textStyle, setTextStyle] = useState<TextStyle>({
    font_family: initialStyle?.font_family ?? "sans",
    font_size: initialStyle?.font_size ?? 16,
  });
  const [text, setText] = useState(initialText);
  const [color, setColor] = useState(initialColor);

  useEffect(() => {
    if (open) {
      setTextStyle({
        font_family: initialStyle?.font_family ?? "sans",
        font_size: initialStyle?.font_size ?? 16,
      });
      setText(initialText);
      setColor(initialColor);
    }
  }, [open, initialText, initialColor, initialStyle?.font_family, initialStyle?.font_size]);

  function handleSave() {
    if (!canEdit || !text.trim()) return;
    onSave(text.trim().slice(0, 1000), color, textStyle);
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
          style={{
            display: "flex",
            justifyContent: "space-between",
            width: "100%",
            alignItems: "center",
          }}
        >
          {onDelete && canEdit ? (
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
            {canEdit && (
              <Button variant="primary" onClick={handleSave} disabled={!text.trim()}>
                Save text
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {authorInfo && (
          <div className={styles.author}>
            <span>
              Added by <strong>{authorInfo.name}</strong>
            </span>
            <span>{authorInfo.time}</span>
          </div>
        )}

        {!canEdit && (
          <p role="status">
            Your contribution permission changed. Copy your draft before closing this window.
          </p>
        )}
        <TextStyleFields style={textStyle} onChange={setTextStyle} />
        <TextArea
          label="Text content"
          value={text}
          onChange={(e) => setText(e.target.value)}
          readOnly={!canEdit}
          maxLength={1000}
          rows={3}
        />

        <div>
          <span
            style={{
              display: "block",
              fontSize: "13px",
              fontWeight: 600,
              marginBottom: "8px",
            }}
          >
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
