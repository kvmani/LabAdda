import type { Dispatch, MutableRefObject, RefObject, SetStateAction } from "react";
import { errorMessage } from "../../api";
import type { useUploadQueue } from "../../components/UploadRecovery";
import type { Workspace } from "../../types";
import type { PendingOp, Region, SaveState, Tool } from "./boardModel";
import { STICKY_COLORS, PEN_COLORS, type DrawMode, type StickyShape, type StickySize } from "./types";
import { STICKY_SHAPES, STICKY_SIZES } from "./shapes";

type Setter<T> = Dispatch<SetStateAction<T>>;
type View = { x: number; y: number; scale: number };

/** Everything the shared board's tool row shows and changes; the board owns the state. */
export type BoardToolbarProps = {
  ws: Workspace & { can_contribute: boolean; can_moderate: boolean };
  panel: boolean;
  tool: Tool;
  setTool: Setter<Tool>;
  drawMode: DrawMode;
  setDrawMode: Setter<DrawMode>;
  color: string;
  setColor: Setter<string>;
  stickyShape: StickyShape;
  setStickyShape: Setter<StickyShape>;
  stickySize: StickySize;
  setStickySize: Setter<StickySize>;
  stickyColor: string;
  setStickyColor: Setter<string>;
  setView: Setter<View>;
  showList: boolean;
  setShowList: Setter<boolean>;
  setSelection: Setter<Region | null>;
  setMessage: Setter<string | null>;
  setTaskContext: Setter<{ epoch: number; revision: number } | null>;
  save: SaveState;
  epoch: number;
  boardIndex: number;
  presence: { id: string; display_name: string }[];
  state: MutableRefObject<{ revision: number; epoch: number }>;
  fileRef: RefObject<HTMLInputElement>;
  uploads: ReturnType<typeof useUploadQueue>;
  mine: boolean;
  submit: (op: Omit<PendingOp, "op_id" | "epoch">) => void;
  fit: () => void;
  openOnPanel: () => Promise<void>;
  restore: () => Promise<void>;
};

/** The shared board's tools, undo, zoom, list view, task, image, snapshot and panel controls. */
export function BoardToolbar(props: BoardToolbarProps) {
  const {
    boardIndex,
    color,
    drawMode,
    epoch,
    fileRef,
    fit,
    mine,
    openOnPanel,
    panel,
    presence,
    restore,
    save,
    setColor,
    setDrawMode,
    setMessage,
    setSelection,
    setShowList,
    setStickyColor,
    setStickyShape,
    setStickySize,
    setTaskContext,
    setTool,
    setView,
    showList,
    state,
    stickyColor,
    stickyShape,
    stickySize,
    submit,
    tool,
    uploads,
    ws,
  } = props;
  return (
    <div className="toolbar" role="toolbar" aria-label="Drawing tools">
      {(["select", "pen", "eraser", "text", "sticky", "pan"] as Tool[])
        .filter((t) => ws.can_contribute || t === "pan")
        .map((t) => (
          <button
            key={t}
            className={"tool" + (tool === t ? " active" : "")}
            aria-pressed={tool === t}
            onClick={() => setTool(t)}
            disabled={!ws.can_contribute && t !== "pan"}
          >
            {t === "select"
              ? "↖ Select"
              : t === "pen"
                ? "✏️ Draw"
                : t === "eraser"
                  ? "🧽 Eraser"
                  : t === "text"
                    ? "🔤 Text"
                    : t === "sticky"
                      ? "🗒 Sticky"
                      : "✋ Pan"}
          </button>
        ))}
      {ws.can_contribute && tool === "pen" && (
        <span className="tool-group" role="radiogroup" aria-label="Drawing tools">
          {(
            [
              { id: "pen", label: "Pen", icon: "✏️" },
              { id: "pencil", label: "Pencil", icon: "✎" },
              { id: "brush", label: "Marker", icon: "🖌️" },
              { id: "line", label: "Line", icon: "╱" },
              { id: "arrow", label: "Arrow", icon: "→" },
              { id: "rect", label: "Box", icon: "▭" },
              { id: "circle", label: "Circle", icon: "◯" },
            ] as { id: DrawMode; label: string; icon: string }[]
          ).map((m) => (
            <button
              key={m.id}
              role="radio"
              aria-checked={drawMode === m.id}
              className={"tool tool--sub" + (drawMode === m.id ? " active" : "")}
              onClick={() => setDrawMode(m.id)}
              title={m.label}
            >
              {m.icon} {m.label}
            </button>
          ))}
        </span>
      )}
      {!panel && ws.can_contribute && (
        <>
          <button
            className="tool"
            onClick={() => fileRef.current?.click()}
            disabled={!ws.can_contribute || uploads.attempts.length > 0}
          >
            🖼 Image
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg"
            hidden
            aria-label="Image to place on the board"
            onChange={(e) => {
              try {
                uploads.queue.add(Array.from(e.target.files ?? []), 1);
              } catch (error: unknown) {
                setMessage(errorMessage(error));
              }
              e.target.value = "";
            }}
          />
          <button
            className={"tool" + (tool === "snapshot" ? " active" : "")}
            aria-pressed={tool === "snapshot"}
            onClick={() => {
              setTool("snapshot");
              setSelection(null);
            }}
          >
            📷 Publish snapshot
          </button>
        </>
      )}
      {ws.can_contribute && tool === "sticky" && (
        <>
          <span className="tool-group" role="radiogroup" aria-label="Sticky note shape">
            {STICKY_SHAPES.map((s) => (
              <button
                key={s.id}
                role="radio"
                aria-checked={stickyShape === s.id}
                aria-label={`${s.label} shape`}
                className={"tool tool--sub tool--shape" + (stickyShape === s.id ? " active" : "")}
                onClick={() => setStickyShape(s.id)}
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
                role="radio"
                aria-checked={stickySize === sz.id}
                aria-label={`${sz.label} size`}
                className={"tool tool--sub" + (stickySize === sz.id ? " active" : "")}
                onClick={() => setStickySize(sz.id)}
                title={`${sz.label} size`}
              >
                {sz.label[0]}
              </button>
            ))}
          </span>
        </>
      )}
      {ws.can_contribute && (
        <span className="swatches" role="radiogroup" aria-label="Colour">
          {(tool === "sticky" ? STICKY_COLORS : PEN_COLORS).map((c) => (
            <button
              key={c}
              role="radio"
              aria-checked={(tool === "sticky" ? stickyColor : color) === c}
              aria-label={`Colour ${c}`}
              className={"swatch" + ((tool === "sticky" ? stickyColor : color) === c ? " active" : "")}
              style={{ background: c }}
              onClick={() => (tool === "sticky" ? setStickyColor(c) : setColor(c))}
            />
          ))}
        </span>
      )}
      {ws.can_contribute && (
        <button
          className="tool"
          onClick={() => submit({ type: "undo" })}
          disabled={!ws.can_contribute || !mine}
        >
          ↶ Undo mine
        </button>
      )}
      <button
        className="tool"
        onClick={() => setView((v) => ({ ...v, scale: Math.min(4, v.scale * 1.25) }))}
        aria-label="Zoom in"
      >
        ＋
      </button>
      <button
        className="tool"
        onClick={() => setView((v) => ({ ...v, scale: Math.max(0.1, v.scale / 1.25) }))}
        aria-label="Zoom out"
      >
        －
      </button>
      <button className="tool" onClick={fit}>
        Fit
      </button>
      <button className="tool" onClick={() => setShowList((v) => !v)} aria-expanded={showList}>
        List view
      </button>
      {!panel && ws.can_moderate && ws.can_contribute && (
        <button className="tool" onClick={restore}>
          Restore…
        </button>
      )}
      {!panel && (
        <button
          className="tool"
          disabled={
            boardIndex !== 0 || state.current.revision === 0 || save === "Saving…" || save === "Reconnecting…"
          }
          title={
            boardIndex === 0
              ? "Create a task reference from this board"
              : "Task references are available on the first board"
          }
          onClick={() => setTaskContext({ ...state.current })}
        >
          Create task from board
        </button>
      )}
      {!panel && (
        <button
          className="tool"
          onClick={openOnPanel}
          disabled={boardIndex !== 0}
          title="Touch panels open the first board"
        >
          📺 Open on touch panel
        </button>
      )}
      <span className={"save-state" + (save === "Saved" ? " ok" : "")} role="status">
        {save}
      </span>
      <span className="board-meta">
        Epoch {epoch} · rev {state.current.revision} · {presence.length} here:{" "}
        {presence.map((p) => p.display_name).join(", ")}
      </span>
    </div>
  );
}
