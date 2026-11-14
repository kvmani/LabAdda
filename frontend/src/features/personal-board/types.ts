import type { StickyShape, StickySize } from "../whiteboard/types";

export type BoardColor = string;

export type BoardObject = {
  id: string;
  kind: "stroke" | "sticky" | "text" | "image";
  color: BoardColor;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  text?: string;
  points?: [number, number][];
  shape?: StickyShape;
  size?: StickySize;
  width?: number;
  asset_id?: string;
  preview_url?: string;
  author?: string;
  created_at?: string;
};

export type BoardDocument = { revision: number; objects: BoardObject[] };
