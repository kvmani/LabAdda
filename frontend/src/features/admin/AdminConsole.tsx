import { Navigate, Route, Routes, useOutletContext } from "react-router-dom";
import { BASE } from "../../config";
import { PageHeader } from "../../ui";
import { Governance } from "../../components/Governance";
import { Operations } from "../../pages/Operations";
import { AdminLayout } from "./AdminLayout";
import { BasicAdministration } from "./BasicAdministration";
import { ActivityPage } from "../activity/ActivityPage";
import { AuditPage } from "../audit/AuditPage";
import { EventsPage } from "../events/EventsPage";
import { HealthPage } from "../health/HealthPage";
import { OrgPage } from "../org/OrgPage";
import { OverviewPage } from "../overview/OverviewPage";
import { PeoplePage } from "../people/PeoplePage";
import { BackupsPage } from "./BackupsPage";
import { Settings } from "./Settings";
import { SetupChecklist } from "./SetupChecklist";
import { SECTIONS, type ConsoleAccess } from "./console";

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
              section.key === "overview" ? (
                <OverviewPage />
              ) : section.key === "people" ? (
                <PeoplePage />
              ) : section.key === "org" ? (
                <OrgPage />
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
                <Navigate to="setup" replace />
              )
            }
          />
        ))}
        <Route path="help/setup" element={<SetupChecklist />} />
        <Route path="people/basic" element={<Basic area="people" />} />
        <Route path="org/basic" element={<Basic area="org" />} />
        <Route path="*" element={null} />
      </Route>
    </Routes>
  );
}
