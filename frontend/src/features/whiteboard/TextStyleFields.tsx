import type { TextStyle } from "./textStyle";

type Props = { style: TextStyle; onChange: (style: TextStyle) => void };
export function TextStyleFields({ style, onChange }: Props) {
  return (
    <fieldset>
      <legend>Text appearance</legend>
      <label htmlFor="board-text-font">Font</label>
      <select
        id="board-text-font"
        value={style.font_family}
        onChange={(e) =>
          onChange({
            ...style,
            font_family: e.target.value as TextStyle["font_family"],
          })
        }
      >
        <option value="sans">Sans serif</option>
        <option value="serif">Serif</option>
        <option value="handwritten">Handwritten (Kalam)</option>
        <option value="mono">Monospace</option>
      </select>
      <label htmlFor="board-text-size">Font size</label>
      <select
        id="board-text-size"
        value={style.font_size}
        onChange={(e) => onChange({ ...style, font_size: Number(e.target.value) })}
      >
        {[8, 12, 14, 16, 20, 24, 28, 32, 40, 48].map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>
    </fieldset>
  );
}
