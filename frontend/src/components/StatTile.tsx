import { STATUS_LABEL, type Status } from "../status";

interface Props {
  label: string;
  value: string;
  detail?: string;
  status?: Status;
}

export function StatTile({ label, value, detail, status }: Props) {
  return (
    <div className="tile" data-status={status}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      <div className="tile-foot">
        {status && (
          <span className={`chip chip-${status}`}>
            <span aria-hidden="true">{STATUS_LABEL[status].icon}</span> {STATUS_LABEL[status].text}
          </span>
        )}
        {detail && <span className="tile-detail">{detail}</span>}
      </div>
    </div>
  );
}
