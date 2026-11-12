import type { Tile } from "./types";
import { comparison, tileValue } from "./model";

/** One figure per tile with its comparison in words; an unmeasured figure says so, never 0. */
export function ActivityTiles({ tiles, period }: { tiles: Tile[]; period: string }) {
  return (
    <ul className="activity-tiles" aria-label="Summary figures">
      {tiles.map((tile) => (
        <li key={tile.key} className="activity-tile">
          <p className="activity-tile__label">{tile.label}</p>
          <p className={`activity-tile__value${tile.value === null ? " activity-tile__value--unknown" : ""}`}>
            {tileValue(tile)}
          </p>
          <p className="activity-tile__note">
            {tile.key === "active_share" && typeof tile.active === "number" && tile.accounts !== undefined
              ? `${tile.active} of ${tile.accounts} accounts. `
              : ""}
            {comparison(tile)}
          </p>
          <p className="activity-tile__period">{period}</p>
        </li>
      ))}
    </ul>
  );
}
