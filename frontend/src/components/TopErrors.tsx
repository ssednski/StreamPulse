import type { ErrorCount } from "../api";
import { formatInt } from "../format";

export function TopErrors({ errors }: { errors: ErrorCount[] }) {
  const max = Math.max(...errors.map((e) => e.count), 1);
  return (
    <section className="card" aria-label="Top errors">
      <header className="card-head">
        <h3>Top playback errors</h3>
        <p>Most frequent fatal error codes in the window</p>
      </header>
      {errors.length === 0 ? (
        <p className="empty">No playback errors in this window.</p>
      ) : (
        <ul className="meter-list">
          {errors.map((e) => (
            <li key={e.errorCode}>
              <span className="meter-name">{e.errorCode}</span>
              <span className="meter-track">
                <span className="meter-fill" style={{ width: `${(e.count / max) * 100}%` }} />
              </span>
              <span className="meter-value">{formatInt(e.count)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
