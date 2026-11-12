import { Sparkline, StatTile } from "../../ui";
import { tileNote, tileStatus, tileValue, trendPoints } from "./model";
import type { Overview } from "./types";

/** Six figures, each with its seven-day trend, freshness and a link to the page behind it. */
export function Tiles({ overview, now }: { overview: Overview; now: number }) {
  return (
    <ul className="overview-tiles" aria-label="Key figures">
      {overview.tiles.map((tile) => (
        <li key={tile.key}>
          <StatTile
            label={tile.label}
            value={tileValue(tile)}
            status={tileStatus(tile)}
            note={tileNote(tile, now)}
            to={tile.link}
          >
            {tile.trend && (
              <Sparkline label={tile.label} points={trendPoints(tile.trend, overview.period.first_day)} />
            )}
            {tile.by_severity && tile.value ? (
              <p className="overview-tile__extra">
                {(["critical", "error", "warning", "info"] as const)
                  .filter((name) => tile.by_severity?.[name])
                  .map((name) => `${tile.by_severity?.[name]} ${name === "info" ? "notice" : name}`)
                  .join(", ")}
              </p>
            ) : null}
          </StatTile>
        </li>
      ))}
    </ul>
  );
}
