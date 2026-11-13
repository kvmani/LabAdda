import { useState, type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import {
  Avatar,
  Badge,
  Banner,
  Breadcrumbs,
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  DataTable,
  DateInput,
  Dialog,
  Drawer,
  EmptyState,
  ErrorState,
  Icon,
  IconButton,
  Menu,
  PageHeader,
  readThemeChoice,
  saveThemeChoice,
  SearchInput,
  Select,
  Skeleton,
  StatTile,
  StatusPill,
  Stepper,
  Switch,
  Tabs,
  Tag,
  TextArea,
  TextInput,
  ToastProvider,
  Tooltip,
  TreeView,
  useToast,
  type Column,
  type HealthStatus,
  type ThemeChoice,
  type TreeNode,
} from "..";
import { ICONS, type IconName } from "../icons";
import { ChartsSection } from "./ChartsSection";
import "./gallery.css";

/*
 * Development-only reference of every ui/ component in every state (U1). main.tsx mounts it at
 * /_ui only when import.meta.env.DEV is true, so it is not part of production builds.
 * All names and data are fictional.
 */

type Person = { id: string; name: string; unit: string; staff: number };
const PEOPLE: Person[] = [
  { id: "p1", name: "Asha Rao", unit: "Thin Films", staff: 6 },
  { id: "p2", name: "Bharat Kulkarni", unit: "Thin Films", staff: 6 },
  { id: "p3", name: "Chitra Iyer", unit: "Corrosion", staff: 9 },
];
const COLUMNS: Column<Person>[] = [
  { key: "name", header: "Name", render: (row) => row.name, sortValue: (row) => row.name },
  { key: "unit", header: "Home unit", render: (row) => row.unit, sortValue: (row) => row.unit },
  {
    key: "staff",
    header: "Unit size",
    render: (row) => row.staff,
    sortValue: (row) => row.staff,
    align: "end",
  },
];
const ORG: TreeNode[] = [
  {
    id: "root",
    label: "Fictional Institute",
    detail: "120 people",
    children: [
      {
        id: "division",
        label: "Surface Engineering Division",
        detail: "24 people",
        children: [
          { id: "thin", label: "Thin Films Section", detail: "6 people" },
          { id: "cat", label: "Corrosion Section", detail: "9 people" },
        ],
      },
      { id: "admin", label: "Administration", detail: "8 people" },
    ],
  },
];
const HEALTH: HealthStatus[] = ["healthy", "degraded", "unavailable", "stale", "unknown", "unsupported"];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="gallery__section" aria-labelledby={`gallery-${title}`}>
      <h2 id={`gallery-${title}`} className="gallery__heading">
        {title}
      </h2>
      <div className="gallery__row">{children}</div>
    </section>
  );
}

function ToastDemo() {
  const toast = useToast();
  return <Button onClick={() => toast("Note saved.")}>Show a confirmation</Button>;
}

function Overlays() {
  const [dialog, setDialog] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [drawer, setDrawer] = useState(false);
  return (
    <>
      <Button onClick={() => setDialog(true)}>Open dialog</Button>
      <Button onClick={() => setConfirm(true)}>Open confirmation</Button>
      <Button onClick={() => setDrawer(true)}>Open drawer</Button>
      <Menu
        label="Actions for Bharat Kulkarni"
        items={[
          { label: "Transfer", icon: "unit", onSelect: () => undefined },
          { label: "Promote", icon: "arrow-up", onSelect: () => undefined, disabled: true },
          { label: "Retire", icon: "user", danger: true, onSelect: () => undefined },
        ]}
      />
      <Tooltip text="A steward looks after a workspace and its members.">
        <button type="button" className="gallery__term">
          Steward
        </button>
      </Tooltip>
      <ToastDemo />
      <Dialog
        open={dialog}
        title="Rename list"
        onClose={() => setDialog(false)}
        footer={
          <>
            <Button variant="quiet" onClick={() => setDialog(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setDialog(false)}>
              Rename list
            </Button>
          </>
        }
      >
        <TextInput label="List name" defaultValue="Sample preparation" />
      </Dialog>
      <ConfirmDialog
        open={confirm}
        title="Retire Deepa Iyer?"
        consequences={[
          "Deepa Iyer can no longer sign in from 30 November 2026.",
          "Surface Engineering Division will have no Head. Choose an acting Head first.",
          "3 open shared tasks stay assigned; their stewards are told to reassign them.",
        ]}
        confirmLabel="Retire 1 person"
        requireReason
        danger
        onConfirm={() => setConfirm(false)}
        onCancel={() => setConfirm(false)}
      />
      <Drawer
        open={drawer}
        title="Asha Rao"
        onClose={() => setDrawer(false)}
        footer={<Button onClick={() => setDrawer(false)}>Close details</Button>}
      >
        <p>Scientific Officer, Thin Films Section. Steward.</p>
        <StatusPill tone="ok" icon="success" label="Active" />
      </Drawer>
    </>
  );
}

export function Gallery() {
  const [theme, setTheme] = useState<ThemeChoice>(readThemeChoice());
  const [switchOn, setSwitchOn] = useState(true);
  const [tab, setTab] = useState("record");
  const [node, setNode] = useState("thin");
  const [query, setQuery] = useState("");
  const matches = PEOPLE.filter((person) => person.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <MemoryRouter>
      <ToastProvider>
        <main className="gallery">
          <PageHeader
            title="Component gallery"
            scope="Development reference for every ui/ component and state. Fictional data."
            helpHref="#gallery"
            action={
              <Select
                label="Colour theme"
                value={theme}
                onChange={(event) => {
                  const choice = event.target.value as ThemeChoice;
                  setTheme(choice);
                  saveThemeChoice(choice);
                }}
                options={[
                  { value: "system", label: "Follow the system" },
                  { value: "light", label: "Light" },
                  { value: "dark", label: "Dark" },
                ]}
              />
            }
          />

          <Section title="Buttons">
            <Button variant="primary" icon="plus">
              Add person
            </Button>
            <Button>Export CSV</Button>
            <Button variant="quiet">Cancel</Button>
            <Button variant="danger">Retire 1 person</Button>
            <Button size="sm">Small</Button>
            <Button variant="primary" busy busyLabel="Saving…">
              Save
            </Button>
            <Button disabled>Unavailable action</Button>
            <IconButton icon="edit" label="Edit record" />
            <IconButton icon="more" label="More actions" variant="secondary" />
          </Section>

          <Section title="Icons">
            <ul className="gallery__icons">
              {(Object.keys(ICONS) as IconName[]).map((name) => (
                <li key={name}>
                  <Icon name={name} />
                  <span>{name}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Form fields">
            <div className="gallery__form">
              <TextInput label="Display name" defaultValue="Asha Rao" />
              <TextInput label="Employee number" hint="Five digits, if your site uses them." />
              <TextInput
                label="Username"
                required
                error="That username is already in use."
                defaultValue="asha"
              />
              <TextInput label="Read-only field" disabled defaultValue="Cannot be changed" />
              <TextArea label="Reason" hint="Kept in the audit trail." />
              <Select
                label="Role"
                placeholder="Choose a role"
                options={[
                  { value: "member", label: "Member" },
                  { value: "steward", label: "Steward" },
                ]}
              />
              <DateInput label="Effective date" />
              <DateInput label="Reminder" kind="datetime-local" />
              <Checkbox label="Keep access to the old unit for 7 days" hint="Ends automatically." />
              <Switch label="Mention alerts" checked={switchOn} onChange={setSwitchOn} />
              <SearchInput
                label="Search people"
                placeholder="Name or username"
                onSearch={setQuery}
                resultCount={query ? matches.length : null}
              />
            </div>
          </Section>

          <Section title="Stat tiles">
            <StatTile label="People active today" value="42 people" note="Today" to="/admin/activity" />
            <StatTile
              label="Last backup"
              value="30 h ago"
              status="degraded"
              note="Updated 3 s ago"
              to="/admin/backups"
            />
            <StatTile label="Storage used" value="Not measured" status="unknown" to="/admin/storage" />
          </Section>

          <Section title="Status and labels">
            {HEALTH.map((status) => (
              <StatusPill key={status} status={status} />
            ))}
            <StatusPill tone="warn" icon="clock" label="On leave" />
            <Tag>Archived</Tag>
            <Tag tone="info">Steward</Tag>
            <Tag tone="ok">Active</Tag>
            <Tag tone="warn">Acting until 31 Jan</Tag>
            <Tag tone="danger">Suspended</Tag>
            <span className="gallery__inline">
              Messages <Badge count={3} label="unread messages" />
            </span>
            <span className="gallery__inline">
              Alerts <Badge count={240} label="unread alerts" />
            </span>
            {PEOPLE.map((person) => (
              <span key={person.id} className="gallery__inline">
                <Avatar id={person.id} name={person.name} />
                {person.name}
              </span>
            ))}
          </Section>

          <Section title="Cards and states">
            <div className="gallery__wide">
              <Banner>The server restarts at 18:00 for about five minutes.</Banner>
              <Banner level="warning">Planned maintenance on Friday: saving is paused from 18:00.</Banner>
              <Card title="Accounts" actions={<Button size="sm">Add person</Button>}>
                Card content with a title and actions.
              </Card>
              <EmptyState title="No lists yet" action={<Button variant="primary">Create a list</Button>}>
                Lists you create here are shared with everyone in Thin Films Section.
              </EmptyState>
              <ErrorState
                message="The server did not answer. Check your connection, then try again."
                onRetry={() => undefined}
              />
              <Skeleton lines={3} label="Loading people…" />
            </div>
          </Section>

          <Section title="Overlays">
            <Overlays />
          </Section>

          <Section title="Navigation">
            <div className="gallery__wide">
              <Breadcrumbs
                items={[
                  { label: "Administration", to: "/admin" },
                  { label: "People", to: "/admin/people" },
                  { label: "Asha Rao" },
                ]}
              />
              <Tabs
                label="Person details"
                selected={tab}
                onSelect={setTab}
                tabs={[
                  { id: "record", label: "Record" },
                  { id: "access", label: "Access" },
                  { id: "timeline", label: "Timeline" },
                ]}
              >
                <p>The {tab} tab.</p>
              </Tabs>
              <Stepper steps={["Choose unit", "Options", "Review", "Done"]} current={2} />
            </div>
          </Section>

          <Section title="Data">
            <div className="gallery__wide">
              <DataTable
                caption="People"
                columns={COLUMNS}
                rows={PEOPLE}
                rowKey={(row) => row.id}
                initialSort={{ key: "name", direction: "ascending" }}
                footer={<Button size="sm">Load more</Button>}
              />
              <DataTable
                caption="Former staff"
                columns={COLUMNS}
                rows={[]}
                rowKey={(row) => row.id}
                empty={{ title: "No former staff", body: "People who retire or leave are listed here." }}
              />
              <DataTable
                caption="Scheduled changes"
                columns={COLUMNS}
                rows={[]}
                rowKey={(row) => row.id}
                loading
              />
              <TreeView
                label="Organisation"
                nodes={ORG}
                selectedId={node}
                onSelect={(chosen) => setNode(chosen.id)}
                initiallyExpanded={["root", "division"]}
              />
            </div>
          </Section>

          <Section title="Charts">
            <ChartsSection />
          </Section>
        </main>
      </ToastProvider>
    </MemoryRouter>
  );
}
