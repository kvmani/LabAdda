import { STICKY_SHAPES, STICKY_SIZES, DRAW_MODES } from "./shapes";
import {
  STICKY_COLORS,
  PEN_COLORS,
  type DrawMode,
  type StickyShape,
  type StickySize,
  type WhiteboardTool,
} from "./types";

type Props = {
  tool: WhiteboardTool;
  onSelectTool: (t: WhiteboardTool) => void;
  drawMode: DrawMode;
  onSelectDrawMode: (m: DrawMode) => void;
  color: string;
  onSelectColor: (c: string) => void;
  stickyShape: StickyShape;
  onSelectStickyShape: (s: StickyShape) => void;
  stickySize: StickySize;
  onSelectStickySize: (sz: StickySize) => void;
  stickyColor: string;
  onSelectStickyColor: (c: string) => void;
  canWrite?: boolean;
  canUndo?: boolean;
  onUndo?: () => void;
  onFit?: () => void;
  onUploadImage?: () => void;
  saveState?: string;
  saveStateOk?: boolean;
  children?: React.ReactNode;
};

const TOOLS: { id: WhiteboardTool; label: string; icon: string }[] = [
  { id: "select", label: "Select", icon: "↖" },
  { id: "pen", label: "Draw", icon: "✏️" },
  { id: "eraser", label: "Eraser", icon: "🧽" },
  { id: "text", label: "Text", icon: "🔤" },
  { id: "sticky", label: "Sticky", icon: "🗒" },
  { id: "pan", label: "Pan", icon: "✋" },
];

export function WhiteboardToolbar({
  tool,
  onSelectTool,
  drawMode,
  onSelectDrawMode,
  color,
  onSelectColor,
  stickyShape,
  onSelectStickyShape,
  stickySize,
  onSelectStickySize,
  stickyColor,
  onSelectStickyColor,
  canWrite = true,
  canUndo = false,
  onUndo,
  onFit,
  onUploadImage,
  saveState,
  saveStateOk,
  children,
}: Props) {
  return (
    <div className="toolbar" role="toolbar" aria-label="Whiteboard tools">
      {TOOLS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={"tool" + (tool === t.id ? " active" : "")}
          aria-pressed={tool === t.id}
          onClick={() => onSelectTool(t.id)}
          disabled={!canWrite && t.id !== "pan"}
          title={`${t.label} tool`}
        >
          {t.icon} {t.label}
        </button>
      ))}

      {onUploadImage && canWrite && (
        <button type="button" className="tool" onClick={onUploadImage} title="Upload and place image">
          🖼 Image
        </button>
      )}

      {tool === "pen" && (
        <>
          <span className="tool-group" role="radiogroup" aria-label="Drawing pen or shape">
            {DRAW_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                role="radio"
                aria-checked={drawMode === m.id}
                className={"tool tool--sub" + (drawMode === m.id ? " active" : "")}
                onClick={() => onSelectDrawMode(m.id)}
                title={m.label}
              >
                {m.icon} {m.label}
              </button>
            ))}
          </span>

          <span className="tool-group swatches" role="radiogroup" aria-label="Pen colour">
            {PEN_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={color === c}
                aria-label={`Pen colour ${c}`}
                className={"swatch" + (color === c ? " active" : "")}
                style={{ background: c }}
                onClick={() => onSelectColor(c)}
              />
            ))}
          </span>
        </>
      )}

      {tool === "sticky" && (
        <>
          <span className="tool-group" role="radiogroup" aria-label="Sticky note shape">
            {STICKY_SHAPES.map((s) => (
              <button
                key={s.id}
                type="button"
                role="radio"
                aria-checked={stickyShape === s.id}
                aria-label={`${s.label} shape`}
                className={"tool tool--sub tool--shape" + (stickyShape === s.id ? " active" : "")}
                onClick={() => onSelectStickyShape(s.id)}
                title={`${s.label} sticky note`}
              >
                {s.icon} {s.label}
              </button>
            ))}
          </span>

          <span className="tool-group" role="radiogroup" aria-label="Sticky note size">
            {STICKY_SIZES.map((sz) => (
              <button
                key={sz.id}
                type="button"
                role="radio"
                aria-checked={stickySize === sz.id}
                aria-label={`${sz.label} size`}
                className={"tool tool--sub" + (stickySize === sz.id ? " active" : "")}
                onClick={() => onSelectStickySize(sz.id)}
                title={`${sz.label} sticky note`}
              >
                {sz.label}
              </button>
            ))}
          </span>

          <span className="tool-group swatches" role="radiogroup" aria-label="Sticky note colour">
            {STICKY_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={stickyColor === c}
                aria-label={`Sticky colour ${c}`}
                className={"swatch" + (stickyColor === c ? " active" : "")}
                style={{ background: c }}
                onClick={() => onSelectStickyColor(c)}
              />
            ))}
          </span>
        </>
      )}

      {onUndo && (
        <button
          type="button"
          className="tool"
          onClick={onUndo}
          disabled={!canUndo || !canWrite}
          title="Undo last action"
        >
          ↶ Undo
        </button>
      )}

      {onFit && (
        <button type="button" className="tool" onClick={onFit} title="Fit board content in view">
          ⛶ Fit
        </button>
      )}

      {children}

      {saveState && (
        <span
          className={"save-state" + (saveStateOk ? " ok" : "")}
          role="status"
          aria-live="polite"
          style={{ marginLeft: "auto", fontSize: "13px" }}
        >
          {saveState}
        </span>
      )}
    </div>
  );
}
