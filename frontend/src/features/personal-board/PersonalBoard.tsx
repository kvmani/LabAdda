import { useEffect, useRef, useState } from "react";
import { useSession } from "../../session";
import { boardDraft, rememberBoard, clearBoardDraft } from "./draft";
import { api, errorMessage } from "../../api";
import { Button, ErrorState, PageHeader, Skeleton, TextArea } from "../../ui";
import { StickyNote } from "./StickyNote";
import type { BoardColor, BoardDocument, BoardObject } from "./types";
import { STICKY_SHAPES, STICKY_SIZES } from "../whiteboard/shapes";
import { STICKY_COLORS, type StickyShape, type StickySize } from "../whiteboard/types";
import "./personal-board.css";

/** A private canvas with explicit durable saves and preserved drafts on conflict or failure. */
export function PersonalBoard() {
  const { session } = useSession();
  const draftKey = `${session?.user.id}:${session?.csrf_token}`;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [document, setDocument] = useState<BoardDocument | null>(null);
  const [objects, setObjects] = useState<BoardObject[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [tool, setTool] = useState<"pen" | "select">("pen");
  const [color, setColor] = useState<BoardColor>("teal");
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [stickyShape, setStickyShape] = useState<StickyShape>("rectangle");
  const [stickySize, setStickySize] = useState<StickySize>("medium");
  const [stickyColor, setStickyColor] = useState<string>(STICKY_COLORS[0]);
  const draft = useRef<BoardObject | null>(null);
  const [preview, setPreview] = useState<BoardObject | null>(null);

  useEffect(() => {
    const savedDraft = boardDraft(draftKey);
    if (savedDraft) {
      setDocument(savedDraft.document);
      setObjects(savedDraft.objects);
      setDirty(true);
      setLoading(false);
      return;
    }
    let active = true;
    api<BoardDocument>("/me/whiteboard")
      .then((result) => {
        if (active) {
          if (!mounted.current) return;
          setDocument(result);
          setObjects(result.objects);
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [draftKey]);

  useEffect(() => {
    if (dirty && document) rememberBoard({ key: draftKey, document, objects });
  }, [dirty, document, draftKey, objects]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function change(next: BoardObject[]) {
    if (next.length > 500) {
      setError("This board has reached its 500-object limit.");
      return;
    }
    setObjects(next);
    setDirty(true);
  }

  async function save() {
    if (!document) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<BoardDocument>("/me/whiteboard", {
        method: "PUT",
        body: { revision: document.revision, objects },
      });
      if (!mounted.current) return;
      setDocument(result);
      setObjects(result.objects);
      setDirty(false);
      clearBoardDraft(draftKey);
    } catch (reason: unknown) {
      if (mounted.current) setError(errorMessage(reason) + " Your draft is still on this page.");
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function reload() {
    if (dirty && !window.confirm("Replace your unsaved draft with the saved version?")) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<BoardDocument>("/me/whiteboard");
      if (!mounted.current) return;
      setDocument(result);
      setObjects(result.objects);
      setDirty(false);
      clearBoardDraft(draftKey);
      setSelected(null);
    } catch (reason: unknown) {
      if (mounted.current) setError(errorMessage(reason));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  function point(event: React.PointerEvent<SVGSVGElement>): [number, number] {
    const rect = event.currentTarget.getBoundingClientRect();
    return [
      Math.max(0, Math.min(1000, ((event.clientX - rect.left) * 1000) / rect.width)),
      Math.max(0, Math.min(600, ((event.clientY - rect.top) * 600) / rect.height)),
    ];
  }

  function start(event: React.PointerEvent<SVGSVGElement>) {
    if (busy || tool !== "pen" || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    draft.current = {
      id: crypto.randomUUID(),
      kind: "stroke",
      color,
      x: 0,
      y: 0,
      text: "",
      points: [point(event)],
    };
    setPreview(draft.current);
  }

  function move(event: React.PointerEvent<SVGSVGElement>) {
    if (!draft.current || draft.current.points.length >= 2000) return;
    draft.current = { ...draft.current, points: [...draft.current.points, point(event)] };
    setPreview(draft.current);
  }

  function finish() {
    if (draft.current) change([...objects, draft.current]);
    draft.current = null;
    setPreview(null);
  }

  function sticky() {
    if (!text.trim()) return;
    change([
      ...objects,
      {
        id: crypto.randomUUID(),
        kind: "sticky",
        color: stickyColor,
        shape: stickyShape,
        size: stickySize,
        x: 60 + (objects.length % 5) * 160,
        y: 60 + (objects.length % 3) * 140,
        text: text.trim(),
        points: [],
      },
    ]);
    setText("");
  }

  function shift(dx: number, dy: number) {
    change(
      objects.map((item) =>
        item.id === selected
          ? {
              ...item,
              x: Math.min(820, Math.max(0, item.x + dx)),
              y: Math.min(460, Math.max(0, item.y + dy)),
            }
          : item,
      ),
    );
  }

  if (loading) return <Skeleton label="Loading your private whiteboard" />;
  return (
    <main className="personal-board">
      <PageHeader title="My Whiteboard" />
      <p>Only you · Draw and collect sticky notes. Nothing here is shared with your teams.</p>
      {error && <ErrorState title="Board not saved or loaded" message={error} />}
      <div className="personal-board__toolbar" aria-label="Whiteboard tools">
        <Button onClick={() => setTool("pen")} aria-pressed={tool === "pen"} disabled={busy}>
          Draw
        </Button>
        <Button onClick={() => setTool("select")} aria-pressed={tool === "select"} disabled={busy}>
          Select notes
        </Button>
        <label>
          Pen colour{" "}
          <select value={color} onChange={(e) => setColor(e.target.value)} disabled={busy}>
            {(["teal", "blue", "orange", "purple"] as const).map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <Button onClick={() => void save()} disabled={busy || !dirty || !document}>
          Save board
        </Button>
        <Button onClick={() => void reload()} disabled={busy}>
          Load saved version
        </Button>
        <Button
          disabled={busy || !objects.length}
          onClick={() => {
            change(objects.slice(0, -1));
            setSelected(null);
          }}
        >
          Undo last object
        </Button>
        <span role="status">{busy ? "Working…" : dirty ? "Unsaved changes" : "Saved version loaded"}</span>
      </div>
      <div className="personal-board__canvas">
        <svg
          viewBox="0 0 1000 600"
          aria-label="Personal drawing canvas"
          role="group"
          onPointerDown={start}
          onPointerMove={move}
          onPointerUp={finish}
          onPointerCancel={() => {
            draft.current = null;
            setPreview(null);
          }}
        >
          {[...objects, ...(preview ? [preview] : [])].map((item) =>
            item.kind === "stroke" ? (
              <polyline
                key={item.id}
                className={`personal-board__stroke board-color-${item.color}`}
                points={item.points.map((p) => p.join(",")).join(" ")}
              />
            ) : null,
          )}
          {objects
            .filter((item) => item.kind === "sticky")
            .map((item) => (
              <StickyNote
                key={item.id}
                item={item}
                busy={busy}
                selected={selected === item.id}
                onSelect={() => {
                  setSelected(item.id);
                  setText(item.text);
                  if (item.shape) setStickyShape(item.shape);
                  if (item.size) setStickySize(item.size);
                  if (item.color) setStickyColor(item.color);
                  setTool("select");
                }}
                onChange={(updated) => change(objects.map((row) => (row.id === updated.id ? updated : row)))}
              />
            ))}
        </svg>
      </div>
      <section className="personal-board__editor" aria-label="Sticky note editor">
        <TextArea
          label="Sticky note text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={1000}
          disabled={busy}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", margin: "10px 0" }}>
          <div>
            <span style={{ fontSize: "13px", fontWeight: 600, marginRight: "8px" }}>Shape:</span>
            <span style={{ display: "inline-flex", gap: "6px", flexWrap: "wrap" }}>
              {STICKY_SHAPES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`tool tool--shape ${stickyShape === s.id ? "active" : ""}`}
                  style={{
                    padding: "4px 8px",
                    borderRadius: "4px",
                    border: stickyShape === s.id ? "2px solid #1565c0" : "1px solid #ccc",
                    background: stickyShape === s.id ? "#e8f0fe" : "white",
                    cursor: "pointer",
                  }}
                  onClick={() => setStickyShape(s.id)}
                >
                  {s.icon} {s.label}
                </button>
              ))}
            </span>
          </div>

          <div>
            <span style={{ fontSize: "13px", fontWeight: 600, marginRight: "8px" }}>Size:</span>
            <span style={{ display: "inline-flex", gap: "6px" }}>
              {STICKY_SIZES.map((sz) => (
                <button
                  key={sz.id}
                  type="button"
                  style={{
                    padding: "4px 10px",
                    borderRadius: "4px",
                    border: stickySize === sz.id ? "2px solid #1565c0" : "1px solid #ccc",
                    background: stickySize === sz.id ? "#e8f0fe" : "white",
                    cursor: "pointer",
                  }}
                  onClick={() => setStickySize(sz.id)}
                >
                  {sz.label}
                </button>
              ))}
            </span>
          </div>

          <div>
            <span style={{ fontSize: "13px", fontWeight: 600, marginRight: "8px" }}>Pastel color:</span>
            <span style={{ display: "inline-flex", gap: "8px", verticalAlign: "middle" }}>
              {STICKY_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  style={{
                    width: "24px",
                    height: "24px",
                    borderRadius: "50%",
                    background: c,
                    border: stickyColor === c ? "2px solid #1f2933" : "1px solid #9aa5b1",
                    cursor: "pointer",
                  }}
                  onClick={() => setStickyColor(c)}
                  aria-label={`Color ${c}`}
                />
              ))}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
          <Button onClick={sticky} disabled={busy || !document || !text.trim()}>
            Add sticky note
          </Button>
          {selected && (
            <>
              <Button
                disabled={busy}
                onClick={() =>
                  change(
                    objects.map((item) =>
                      item.id === selected
                        ? {
                            ...item,
                            text,
                            shape: stickyShape,
                            size: stickySize,
                            color: stickyColor,
                          }
                        : item,
                    ),
                  )
                }
              >
                Update selected note
              </Button>
              <Button
                variant="danger"
                disabled={busy}
                onClick={() => {
                  change(objects.filter((item) => item.id !== selected));
                  setSelected(null);
                  setText("");
                }}
              >
                Erase note
              </Button>
            </>
          )}
        </div>

        {selected && (
          <div className="personal-board__toolbar" style={{ marginTop: "10px" }}>
            <span style={{ fontSize: "13px", fontWeight: 600 }}>Move note:</span>
            <Button disabled={busy} onClick={() => shift(-20, 0)}>
              Left
            </Button>
            <Button disabled={busy} onClick={() => shift(20, 0)}>
              Right
            </Button>
            <Button disabled={busy} onClick={() => shift(0, -20)}>
              Up
            </Button>
            <Button disabled={busy} onClick={() => shift(0, 20)}>
              Down
            </Button>
          </div>
        )}
      </section>
      <p>Choose a note to edit or move it with the arrow keys. Save before leaving this page.</p>
    </main>
  );
}
