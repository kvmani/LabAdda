import { Route, Routes, useOutletContext } from "react-router-dom";
import { BASE } from "../../config";
import { EmptyState, PageHeader } from "../../ui";
import { Governance } from "../../components/Governance";
import { Operations } from "../../pages/Operations";
import { AdminLayout } from "./AdminLayout";
import { BasicAdministration } from "./BasicAdministration";
import { ActivityPage } from "../activity/ActivityPage";
import { AuditPage } from "../audit/AuditPage";
import { EventsPage } from "../events/EventsPage";
import { HealthPage } from "../health/HealthPage";
import { PeoplePage } from "../people/PeoplePage";
import { BackupsPage } from "./BackupsPage";
import { Settings } from "./Settings";
import { SECTIONS, type ConsoleAccess } from "./console";

function Placeholder({ title }: { title: string }) {
  return (
    <>
      <PageHeader
        title={title}
        scope="Site administration without opening anyone’s private work."
        helpHref={BASE + "/admin/help"}
      />
      <EmptyState title="Not available yet">
        This section will be added in a future update. Choose an available tool from the administration
        navigation.
      </EmptyState>
    </>
  );
}
function Basic({ area }: { area: "people" | "org" }) {
  return (
    <>
      <PageHeader
        title={area === "people" ? "People (basic)" : "Organisation (basic)"}
        scope="Manage accounts and access without reading private work."
        helpHref={BASE + "/admin/help"}
      />
      <BasicAdministration area={area} />
    </>
  );
}
function Storage() {
  const { read_only } = useOutletContext<ConsoleAccess>();
  return (
    <>
      <PageHeader
        title="Storage"
        scope="Storage figures are incomplete. These tools show sizes and counts, not private work."
        helpHref={BASE + "/admin/help"}
      />
      {read_only ? <Operations /> : <Governance />}
    </>
  );
}
/** Route-bound console chunk keeps administration out of the initial application load. */
export function AdminConsole() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        {SECTIONS.map((section) => (
          <Route
            key={section.key}
            path={section.key === "overview" ? "" : section.key}
            element={
              section.key === "people" ? (
                <PeoplePage />
              ) : section.key === "org" ? (
                <Basic area="org" />
              ) : section.key === "audit" ? (
                <AuditPage />
              ) : section.key === "activity" ? (
                <ActivityPage />
              ) : section.key === "health" ? (
                <HealthPage />
              ) : section.key === "events" ? (
                <EventsPage />
              ) : section.key === "storage" ? (
                <Storage />
              ) : section.key === "backups" ? (
                <BackupsPage />
              ) : section.key === "settings" ? (
                <Settings />
              ) : (
                <Placeholder title={section.label} />
              )
            }
          />
        ))}
        <Route path="people/basic" element={<Basic area="people" />} />
        <Route path="*" element={null} />
      </Route>
    </Routes>
  );
}
