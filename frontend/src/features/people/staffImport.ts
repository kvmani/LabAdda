import { api, errorCode, errorMessage, errorStatus } from "../../api";
import type { BulkReceipt, ChangePlan } from "./changeTypes";

export type StaffRow = {
  line: number;
  display_name: string;
  username: string;
  place: string;
  role: "member" | "admin";
  access: "code" | "password" | "off";
  errors: string[];
  warnings: string[];
};
export type StaffReport = {
  rows: StaffRow[];
  total: number;
  errors: number;
  units_to_create: { name: string; level: "group" | "division" | "section"; under: string[] }[];
  administrators: string[];
  plan: ChangePlan | null;
};

export const SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
export const MAX_BYTES = 1024 * 1024;

/** CSV files go up as text, workbooks as their own type; the server reads both the same way. */
export function typeOf(file: File): string | null {
  const name = file.name.toLowerCase();
  if (name.endsWith(".xlsx")) return SHEET_TYPE;
  if (name.endsWith(".csv")) return "text/csv";
  return null;
}

export function reviewFile(file: File): Promise<StaffReport> {
  return api<StaffReport>("/admin/changes/import/staff/preview", {
    raw: { data: file, type: typeOf(file) ?? SHEET_TYPE },
  });
}

export function applyFile(file: File, digest: string, reason: string): Promise<BulkReceipt> {
  return api<BulkReceipt>("/admin/changes/import/staff/apply", {
    raw: { data: file, type: typeOf(file) ?? SHEET_TYPE },
    headers: { "X-Import-Digest": digest, "X-Import-Reason": encodeURIComponent(reason) },
  });
}

export async function downloadTemplate(): Promise<void> {
  const blob = await api<Blob>("/admin/changes/import/staff/template", { responseType: "blob" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "staff-import-template.xlsx";
  link.click();
  URL.revokeObjectURL(link.href);
}

/** Plain words for a failed review or apply; the chosen file is kept so the person can retry. */
export function describeFailure(error: unknown): string {
  if (errorStatus(error) === 409)
    return "Something changed since you reviewed this file. Choose the file again to review a fresh plan.";
  if (errorCode(error) === "offline") return errorMessage(error);
  return errorMessage(error);
}
