export type SettingItem = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  unit: string;
  explanation: string;
  changed_by: string;
};
export type SettingGroup = { key: string; title: string; summary: string; items: SettingItem[] };
export type SettingsPayload = { groups: SettingGroup[] };
