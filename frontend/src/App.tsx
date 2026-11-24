import { lazy, Suspense, useEffect } from "react";
import { EmptyState, PageHeader, Skeleton } from "./ui";
import { AdminBoundary } from "./features/admin/AdminBoundary";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Shell } from "./features/shell/Shell";
import { useSession } from "./session";
import { WorkspaceProvider } from "./workspaces";
import { PageChunk } from "./components/PageChunk";
import { Activate, Login } from "./pages/Login";

import { ForcedPasswordChange } from "./features/profile/ForcedPasswordChange";
import { HelpBoundary } from "./features/help/HelpBoundary";

import { Home, Landing } from "./features/home/Home";
import { clearBoardDraft, hasBoardDrafts } from "./features/personal-board/draft";

const JoinPage = lazy(() => import("./pages/JoinPage").then((module) => ({ default: module.JoinPage })));
const WorkspaceView = lazy(() =>
  import("./pages/WorkspaceView").then((module) => ({ default: module.WorkspaceView })),
);
const MyTasks = lazy(() => import("./pages/MyTasks").then((module) => ({ default: module.MyTasks })));
const Todos = lazy(() => import("./pages/Todos").then((module) => ({ default: module.Todos })));
const Notes = lazy(() => import("./pages/Notes").then((module) => ({ default: module.Notes })));
const NewGroup = lazy(() => import("./pages/NewGroup").then((module) => ({ default: module.NewGroup })));
const Usage = lazy(() => import("./pages/Usage").then((module) => ({ default: module.Usage })));
const ProfilePage = lazy(() =>
  import("./features/profile/ProfilePage").then((module) => ({ default: module.ProfilePage })),
);
const AlertPreferences = lazy(() =>
  import("./pages/AlertPreferences").then((module) => ({ default: module.AlertPreferences })),
);
const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })));
const PersonalBoard = lazy(() =>
  import("./features/personal-board/PersonalBoard").then((module) => ({ default: module.PersonalBoard })),
);
const Directory = lazy(() => import("./pages/Directory").then((module) => ({ default: module.Directory })));
const CalendarPage = lazy(() =>
  import("./pages/CalendarPage").then((module) => ({ default: module.CalendarPage })),
);
const Admin = lazy(() => import("./pages/Admin"));
const Help = lazy(() => import("./pages/Help"));

export function App() {
  const { session, loading } = useSession();
  const location = useLocation();
  useEffect(() => {
    if (!session) clearBoardDraft();
  }, [session]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (hasBoardDrafts()) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);
  if (loading) return <Skeleton label="Loading LabAdda…" lines={3} />;
  if (!session) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/activate" element={<Activate />} />
        <Route
          path="/join"
          element={
            <PageChunk label="Loading the join form">
              <JoinPage />
            </PageChunk>
          }
        />
        <Route path="*" element={<Login next={location.pathname + location.search} />} />
      </Routes>
    );
  }
  if (session.must_change_password) return <ForcedPasswordChange />;
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
          <Route path="/join" element={<Navigate to="/" replace />} />
          <Route
            path="/w/:workspaceId"
            element={
              <PageChunk label="Loading the workspace">
                <WorkspaceView />
              </PageChunk>
            }
          />
          <Route
            path="/w/:workspaceId/:tab"
            element={
              <PageChunk label="Loading the workspace">
                <WorkspaceView />
              </PageChunk>
            }
          />
          <Route
            path="/calendar"
            element={
              <PageChunk label="Loading the calendar">
                <CalendarPage />
              </PageChunk>
            }
          />
          <Route
            path="/profile"
            element={
              <PageChunk label="Loading your profile">
                <ProfilePage />
              </PageChunk>
            }
          />
          <Route
            path="/directory"
            element={
              <PageChunk label="Loading the staff directory">
                <Directory />
              </PageChunk>
            }
          />
          <Route
            path="/preferences"
            element={
              <PageChunk label="Loading alert preferences">
                <AlertPreferences />
              </PageChunk>
            }
          />
          <Route
            path="/today"
            element={
              <PageChunk label="Loading today">
                <Dashboard />
              </PageChunk>
            }
          />
          <Route
            path="/my-tasks"
            element={
              <PageChunk label="Loading your tasks">
                <MyTasks />
              </PageChunk>
            }
          />
          <Route
            path="/todos"
            element={
              <PageChunk label="Loading your to-do lists">
                <Todos />
              </PageChunk>
            }
          />
          <Route
            path="/notes"
            element={
              <PageChunk label="Loading your notes">
                <Notes />
              </PageChunk>
            }
          />
          <Route
            path="/whiteboard"
            element={
              <PageChunk label="Loading your whiteboard">
                <PersonalBoard key={session.user.id} />
              </PageChunk>
            }
          />
          <Route
            path="/usage"
            element={
              <PageChunk label="Loading storage usage">
                <Usage />
              </PageChunk>
            }
          />
          <Route path="/operations" element={<Navigate to="/admin/storage" replace />} />
          <Route
            path="/groups/new"
            element={
              <PageChunk label="Loading">
                <NewGroup />
              </PageChunk>
            }
          />
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
