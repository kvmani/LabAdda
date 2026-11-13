import { Link } from "react-router-dom";
import { BASE } from "../../config";
import { useSession } from "../../session";
import { useWorkspaces } from "../../workspaces";
import { Skeleton } from "../../ui";
import { Login } from "../../pages/Login";
import { BuildFooter } from "../shell/BuildFooter";
import { Brand } from "./Brand";
import "./home.css";

/** Public welcome page; only fictional research artwork is visible before sign-in. */
export function Landing() {
  return (
    <main className="landing">
      <header className="landing__header">
        <Link to="/" aria-label="LabAdda home">
          <Brand />
        </Link>
        <nav aria-label="Welcome navigation">
          <a href="#features">Features</a>
          <Link to="/login">Sign in</Link>
        </nav>
      </header>
      <section className="landing__hero">
        <div>
          <h1>
            A place for ideas.
            <br />A space for your team.
          </h1>
          <p>A simple intranet collaboration platform for research teams.</p>
          <p>Your team’s work, on your organisation’s network.</p>
          <div className="landing__actions">
            <Link className="ui-button ui-button--primary ui-button--md" to="/login">
              Sign in
            </Link>
            <a className="ui-button ui-button--secondary ui-button--md" href="#features">
              Explore features
            </a>
          </div>
        </div>
        <figure>
          <img
            src={`${BASE}/research-board.png`}
            alt="Illustrative team whiteboard: tensile specimen, stress–strain curve and microstructure, with comments from fictional colleagues."
          />
          <figcaption>Structure Of Materials Section · Illustrative research discussion</figcaption>
        </figure>
      </section>
      <section id="features" className="landing__features" aria-label="Features">
        <article>
          <h2>Share updates</h2>
          <p>Keep notices, files and conversations with the right team.</p>
        </article>
        <article>
          <h2>Draw together</h2>
          <p>Sketch on a team whiteboard, or think privately on My Whiteboard.</p>
        </article>
        <article>
          <h2>Turn ideas into tasks</h2>
          <p>Capture next steps, assign work and follow progress.</p>
        </article>
      </section>
      <Login next="/" embedded />
      <footer>
        <p>People, ideas and lab work.</p>
        <BuildFooter tone="inverse" />
      </footer>
    </main>
  );
}

/** Useful personal tools alongside actual current-access workspace links. */
export function Home() {
  const { session } = useSession();
  const { workspaces, loading } = useWorkspaces();
  return (
    <main className="member-home">
      <h1>Welcome, {session?.user.display_name}</h1>
      <p>Your personal space and your team’s work, together.</p>
      <section className="home-cards" aria-label="Your tools">
        <Link to="/whiteboard">
          <h2>My Whiteboard</h2>
          <p>Only you · Sketch and collect sticky notes.</p>
          <span>Open your board →</span>
        </Link>
        <Link to="/notes">
          <h2>My Notes</h2>
          <p>Only you · Keep personal notes and reminders.</p>
          <span>Open your notes →</span>
        </Link>
        <Link to="/today">
          <h2>My day</h2>
          <p>Follow your tasks, deadlines and updates.</p>
          <span>See your day →</span>
        </Link>
      </section>
      <section aria-label="Team spaces">
        <h2>Your team spaces</h2>
        {loading ? (
          <Skeleton label="Loading workspaces" />
        ) : !workspaces.length ? (
          <p>
            You are not a member of any workspace. Ask an administrator, or{" "}
            <Link to="/groups/new">Create a group</Link>.
          </p>
        ) : (
          <div className="home-cards">
            {workspaces.map((workspace) => (
              <Link key={workspace.id} to={`/w/${workspace.id}/noticeboard`}>
                <h3>{workspace.name}</h3>
                <p>Shared notices, drawing, chat and tasks →</p>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
