import { Link } from "react-router-dom";
import { BASE } from "../../config";
import { Login } from "../../pages/Login";
import { BuildFooter } from "../shell/BuildFooter";
import { Brand } from "./Brand";
import { FaqSection } from "./FaqSection";
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
      <div className="landing__faq">
        <FaqSection defaultOpenId="official-platform" />
      </div>
      <Login next="/" embedded />
      <footer>
        <p>People, ideas and lab work.</p>
        <BuildFooter tone="inverse" />
      </footer>
    </main>
  );
}
