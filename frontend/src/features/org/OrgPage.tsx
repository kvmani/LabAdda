import { useCallback, useState } from "react";
import type { OrgUnit } from "./types";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api";
import { BASE } from "../../config";
import { Banner, Checkbox, ErrorState, PageHeader, Skeleton } from "../../ui";
import { TransferDialog } from "../people/TransferDialog";
import type { StaffRecord, Unit } from "../people/types";
import { OrgChart } from "./OrgChart";
import { OrgSearch } from "./OrgSearch";
import { SpacesList } from "./SpacesList";
import {
  CloseUnitDialog,
  CreateUnitDialog,
  MergeUnitDialog,
  MoveUnitDialog,
  RenameUnitDialog,
  SplitUnitDialog,
} from "./UnitDialogs";
import { UnitPanel, type UnitAction } from "./UnitPanel";
import { useDrag, type DragPayload } from "./useDrag";
import { useOrgTree } from "./useOrgTree";
import "./org.css";

type Dialog =
  | { type: "unit"; action: UnitAction; unitId: string; targetId?: string }
  | { type: "transfer"; person: StaffRecord; unitId: string };

/** Authority loss unmounts the chart and its staff data together, as on the People page. */
export function OrgPage() {
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  if (denied)
    return (
      <ErrorState
        title="Your administration access changed"
        message="The organisation chart has been cleared. Reload to check access again."
        onRetry={() => window.location.reload()}
        retryLabel="Check administration access"
      />
    );
  return <Organisation onDenied={onDenied} />;
}

function Organisation({ onDenied }: { onDenied: () => void }) {
  const tree = useOrgTree(onDenied);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [problem, setProblem] = useState("");
  const [refresh, setRefresh] = useState(0);

  async function transfer(personId: string, unitId: string) {
    setProblem("");
    try {
      const person = await api<StaffRecord>(`/admin/people/${encodeURIComponent(personId)}`);
      setDialog({ type: "transfer", person, unitId });
    } catch (error: unknown) {
      setProblem(errorMessage(error));
    }
  }
  function dropped(payload: DragPayload, unitId: string) {
    if (payload.kind === "person") void transfer(payload.id, unitId);
    else setDialog({ type: "unit", action: "move", unitId: payload.id, targetId: unitId });
  }
  const drag = useDrag(dropped);
  const done = () => {
    tree.refresh();
    setRefresh((value) => value + 1);
  };
  const close = () => setDialog(null);
  const unitDialog = dialog?.type === "unit" ? tree.all.find((item) => item.id === dialog.unitId) : undefined;
  const common = { units: tree.all, onClose: close, onDenied, onDone: done };
  const asUnits: Unit[] = tree.all.map((item) => ({
    id: item.id,
    name: item.name,
    kind: "org",
    parent_id: item.parent_id,
    archived: item.archived,
  }));
  const status = drag.active
    ? `Moving ${drag.active.payload.label}. Release over a unit to review the change, or press Escape to cancel.`
    : "";
  return (
    <>
      <PageHeader
        title="Organisation"
        scope="Units, their heads and how many people they hold. Names, roles and counts only."
        helpHref={BASE + "/admin/help"}
        action={<Link to="/admin/org/basic">Basic project tools</Link>}
      />
      <p className="org-status" role="status" aria-live="polite">
        {status}
      </p>
      {problem && <Banner level="warning">{problem}</Banner>}
      {tree.error ? (
        <ErrorState message={tree.error} onRetry={tree.refresh} />
      ) : !tree.data ? (
        <Skeleton label="Loading the organisation" />
      ) : (
        <div className="org-layout">
          <div className="org-layout__chart">
            <div className="org-layout__tools">
              <OrgSearch units={tree.all} onReveal={tree.show} onDenied={onDenied} />
              <Checkbox
                label="Show closed units"
                checked={tree.showClosed}
                onChange={(event) => tree.setShowClosed(event.target.checked)}
              />
            </div>
            <OrgChart
              units={tree.units}
              selectedId={tree.selectedId}
              collapsed={tree.collapsed}
              overId={drag.active?.over ?? null}
              onSelect={tree.show}
              onToggle={tree.toggle}
              onCollapseAll={tree.collapseAll}
              onDragStart={drag.start}
              wasDrag={drag.wasDrag}
            />
          </div>
          <aside className="org-layout__side" aria-label="Selected unit">
            {tree.selected ? (
              <UnitPanel
                key={tree.selected.id}
                unit={tree.selected}
                units={tree.all}
                isRoot={!tree.selected.parent_id}
                refreshKey={refresh}
                onSelect={tree.show}
                onAction={(action) => setDialog({ type: "unit", action, unitId: tree.selected?.id ?? "" })}
                onTransfer={(id) => void transfer(id, "")}
                onDragStart={drag.start}
                onDenied={onDenied}
              />
            ) : (
              <p className="org-layout__hint">Choose a unit in the chart to see its people and actions.</p>
            )}
            <SpacesList spaces={tree.data.spaces} />
          </aside>
        </div>
      )}
      {dialog?.type === "transfer" && (
        <TransferDialog
          person={dialog.person}
          units={asUnits}
          initialUnitId={dialog.unitId}
          onClose={close}
          onDenied={onDenied}
          onDone={done}
        />
      )}
      {unitDialog && dialog?.type === "unit" && (
        <UnitDialog action={dialog.action} unit={unitDialog} targetId={dialog.targetId} {...common} />
      )}
    </>
  );
}

function UnitDialog({
  action,
  targetId,
  ...props
}: {
  action: UnitAction;
  targetId?: string;
  unit: OrgUnit;
  units: OrgUnit[];
  onClose: () => void;
  onDenied: () => void;
  onDone: () => void;
}) {
  if (action === "create") return <CreateUnitDialog {...props} />;
  if (action === "rename") return <RenameUnitDialog {...props} />;
  if (action === "move") return <MoveUnitDialog {...props} initialTarget={targetId} />;
  if (action === "merge") return <MergeUnitDialog {...props} />;
  if (action === "split") return <SplitUnitDialog {...props} />;
  return <CloseUnitDialog {...props} />;
}
