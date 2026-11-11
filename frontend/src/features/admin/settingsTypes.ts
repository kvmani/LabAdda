export type SettingItem = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  unit: string;
  explanation: string;
  changed_by: string;
};
export type SettingGroup = { key: string; title: string; summary: string; items: SettingItem[] };
export type Notice = {
  message: string;
  level: "info" | "warning";
  starts_at: string;
  ends_at: string;
  revision: number;
};
export type SettingsPayload = { groups: SettingGroup[]; banner: Notice | null; banner_max_length: number };
