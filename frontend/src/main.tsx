import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { BASE, PANEL } from "./config";
import { PanelApp } from "./pages/Panel";
import { SessionProvider } from "./session";
import "./ui/tokens.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {PANEL ? (
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
