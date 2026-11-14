import type { StickyShape, StickySize } from "../whiteboard/types";

export type BoardColor = string;
export type BoardObject = {
  id: string;
  kind: "stroke" | "sticky";
  color: BoardColor;
  x: number;
  y: number;
  text: string;
  points: [number, number][];
  shape?: StickyShape;
  size?: StickySize;
};
export type BoardDocument = { revision: number; objects: BoardObject[] };
