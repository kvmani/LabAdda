import { lazy, Suspense } from "react";
import { EmptyState, PageHeader, Skeleton } from "./ui";
import { AdminBoundary } from "./features/admin/AdminBoundary";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Shell } from "./features/shell/Shell";
import { useSession } from "./session";
import { WorkspaceProvider, useWorkspaces } from "./workspaces";
import { Activate, Login } from "./pages/Login";
import { WorkspaceView } from "./pages/WorkspaceView";
import { MyTasks } from "./pages/MyTasks";
import { Todos } from "./pages/Todos";
import { Notes } from "./pages/Notes";
import { NewGroup } from "./pages/NewGroup";
import { Usage } from "./pages/Usage";

import { ProfilePage } from "./features/profile/ProfilePage";
import { AlertPreferences } from "./pages/AlertPreferences";
import { Dashboard } from "./pages/Dashboard";
import { HelpBoundary } from "./features/help/HelpBoundary";

const Admin = lazy(() => import("./pages/Admin"));
const Help = lazy(() => import("./pages/Help"));

function Home() {
  const { homeId, workspaces, loading } = useWorkspaces();
  if (loading) return <Skeleton label="Loading workspaces…" lines={3} />;
  const target = homeId ?? workspaces[0]?.id;
  if (target) return <Navigate to={`/w/${target}/noticeboard`} replace />;
  return (
    <>
      <PageHeader title="No workspaces yet" />
      <EmptyState
        title="You are not a member of any workspace"
        action={
          <Link className="ui-button ui-button--primary ui-button--md" to="/groups/new">
            <span>Create a group</span>
          </Link>
        }
      >
        Ask an administrator to add you, or start a collaborative group with colleagues. You can also open{" "}
        <Link to="/notes">My Notes</Link>.
      </EmptyState>
    </>
  );
}

export function App() {
  const { session, loading } = useSession();
  const location = useLocation();
  if (loading) return <Skeleton label="Loading LabAdda…" lines={3} />;
  if (!session) {
    return (
      <Routes>
        <Route path="/activate" element={<Activate />} />
        <Route path="*" element={<Login next={location.pathname + location.search} />} />
      </Routes>
    );
  }
  return (
    <WorkspaceProvider>
      <Shell>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route
            path="/login"
            element={<Navigate to={new URLSearchParams(location.search).get("next") || "/"} replace />}
          />
          <Route path="/activate" element={<Navigate to="/" replace />} />
          <Route path="/w/:workspaceId" element={<WorkspaceView />} />
          <Route path="/w/:workspaceId/:tab" element={<WorkspaceView />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/preferences" element={<AlertPreferences />} />
          <Route path="/today" element={<Dashboard />} />
          <Route path="/my-tasks" element={<MyTasks />} />
          <Route path="/todos" element={<Todos />} />
          <Route path="/notes" element={<Notes />} />
          <Route path="/usage" element={<Usage />} />
          <Route path="/operations" element={<Navigate to="/admin/storage" replace />} />
          <Route path="/groups/new" element={<NewGroup />} />
          <Route
            path="/help/*"
            element={
              <HelpBoundary>
                <Suspense fallback={<Skeleton label="Loading help" />}>
                  <Help />
                </Suspense>
              </HelpBoundary>
            }
          />
          <Route
            path="/admin/*"
            element={
              <AdminBoundary>
                <Suspense fallback={<Skeleton label="Loading administration" />}>
                  <Admin key={session.user.id} />
                </Suspense>
              </AdminBoundary>
            }
          />
          <Route
            path="*"
            element={
              <>
                <PageHeader title="Page not found" />
                <EmptyState title="This page does not exist or you cannot open it">
                  <Link to="/">Go to your home workspace</Link>
                </EmptyState>
              </>
            }
          />
        </Routes>
      </Shell>
    </WorkspaceProvider>
  );
}
