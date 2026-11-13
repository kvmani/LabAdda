export type BoardColor = "teal" | "blue" | "orange" | "yellow" | "mint" | "pink" | "purple";
export type BoardObject = {
  id: string;
  kind: "stroke" | "sticky";
  color: BoardColor;
  x: number;
  y: number;
  text: string;
  points: [number, number][];
};
export type BoardDocument = { revision: number; objects: BoardObject[] };
