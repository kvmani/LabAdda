export type TextStyle = {
  font_family: "sans" | "serif" | "mono" | "handwritten";
  font_size: number;
};
export const BOARD_FONTS = {
  sans: "LabAdda Sans",
  serif: "LabAdda Serif",
  mono: "LabAdda Mono",
  handwritten: "LabAdda Handwriting",
} as const;
export function canvasFont(style: Partial<TextStyle>): string {
  return `${style.font_size ?? 16}px "${BOARD_FONTS[style.font_family ?? "sans"]}"`;
}
export async function loadBoardFonts(): Promise<void> {
  await Promise.all(Object.values(BOARD_FONTS).map((family) => document.fonts.load(`16px "${family}"`)));
}
