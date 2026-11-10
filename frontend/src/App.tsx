import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Shell } from "./components/Shell";
import { useSession } from "./session";
import { WorkspaceProvider, useWorkspaces } from "./workspaces";
import { Activate, Login } from "./pages/Login";
import { WorkspaceView } from "./pages/WorkspaceView";
import { Todos } from "./pages/Todos";
import { Notes } from "./pages/Notes";
import { NewGroup } from "./pages/NewGroup";
import { Operations } from "./pages/Operations";
import { Usage } from "./pages/Usage";
import { Admin } from "./pages/Admin";

function Home() {
  const { homeId, workspaces, loading } = useWorkspaces();
  if (loading) return <p className="state">Loading workspaces…</p>;
  const target = homeId ?? workspaces[0]?.id;
  if (target) return <Navigate to={`/w/${target}/noticeboard`} replace />;
  return (
    <section className="state empty" aria-live="polite">
      <h1>No workspaces yet</h1>
      <p>You are not a member of any workspace. Ask an administrator to add you, or start a collaborative group with colleagues.</p>
      <p>
        <Link className="button" to="/groups/new">Create a group</Link> or open <Link to="/notes">My Notes</Link>.
      </p>
    </section>
  );
}

export function App() {
  const { session, loading } = useSession();
  const location = useLocation();
  if (loading) return <p className="state">Loading LabAdda…</p>;
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
          <Route path="/login" element={<Navigate to={new URLSearchParams(location.search).get("next") || "/"} replace />} />
          <Route path="/activate" element={<Navigate to="/" replace />} />
          <Route path="/w/:workspaceId" element={<WorkspaceView />} />
          <Route path="/w/:workspaceId/:tab" element={<WorkspaceView />} />
          <Route path="/todos" element={<Todos />} />
          <Route path="/notes" element={<Notes />} />
          <Route path="/usage" element={<Usage />} />
          <Route path="/operations" element={<Operations />} />
          <Route path="/groups/new" element={<NewGroup />} />
          <Route path="/admin" element={session.user.is_admin ? <Admin /> : <Navigate to="/" replace />} />
          <Route path="*" element={<section className="state"><h1>Page not found</h1><Link to="/">Go to your home workspace</Link></section>} />
        </Routes>
      </Shell>
    </WorkspaceProvider>
  );
}
