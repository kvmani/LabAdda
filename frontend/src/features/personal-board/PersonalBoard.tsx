import { useEffect, useRef, useState } from "react";
import { useSession } from "../../session";
import { boardDraft, rememberBoard, clearBoardDraft } from "./draft";
import { api, errorMessage } from "../../api";
import { Button, ErrorState, PageHeader, Skeleton, TextArea } from "../../ui";
import { StickyNote } from "./StickyNote";
import type { BoardColor, BoardDocument, BoardObject } from "./types";
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
        color: "yellow",
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
          <select value={color} onChange={(e) => setColor(e.target.value as BoardColor)} disabled={busy}>
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
        <Button onClick={sticky} disabled={busy || !document || !text.trim()}>
          Add sticky note
        </Button>
        {selected && (
          <>
            <Button
              disabled={busy}
              onClick={() => change(objects.map((item) => (item.id === selected ? { ...item, text } : item)))}
            >
              Update selected note
            </Button>
            <label>
              Note colour{" "}
              <select
                disabled={busy}
                value={objects.find((item) => item.id === selected)?.color ?? "yellow"}
                onChange={(e) =>
                  change(
                    objects.map((item) =>
                      item.id === selected ? { ...item, color: e.target.value as BoardColor } : item,
                    ),
                  )
                }
              >
                {(["yellow", "mint", "pink", "purple"] as const).map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <div className="personal-board__toolbar">
              <Button disabled={busy} onClick={() => shift(-20, 0)}>
                Move left
              </Button>
              <Button disabled={busy} onClick={() => shift(20, 0)}>
                Move right
              </Button>
              <Button disabled={busy} onClick={() => shift(0, -20)}>
                Move up
              </Button>
              <Button disabled={busy} onClick={() => shift(0, 20)}>
                Move down
              </Button>
            </div>
          </>
        )}
      </section>
      <p>Choose a note to edit or move it with the arrow keys. Save before leaving this page.</p>
    </main>
  );
}
