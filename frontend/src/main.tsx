// Global styles load first so component and shell styles, imported below, take precedence.
import "./ui/tokens.css";
import "./styles.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { BASE, PANEL } from "./config";
import { PanelApp } from "./pages/Panel";
import { SessionProvider } from "./session";

// The component gallery exists only in development builds; production removes this branch.
const Gallery = import.meta.env.DEV
  ? React.lazy(() => import("./ui/gallery/Gallery").then((module) => ({ default: module.Gallery })))
  : null;
const showGallery = Gallery !== null && window.location.pathname.slice(BASE.length) === "/_ui";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {showGallery && Gallery ? (
      <React.Suspense fallback={null}>
        <Gallery />
      </React.Suspense>
    ) : PANEL ? (
      <PanelApp />
    ) : (
      <BrowserRouter basename={BASE || "/"}>
        <SessionProvider>
          <App />
        </SessionProvider>
      </BrowserRouter>
    )}
  </React.StrictMode>,
);
