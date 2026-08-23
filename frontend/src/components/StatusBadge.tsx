import type { SolverStatus, VersionStatus } from "../types";

export function StatusBadge({ status }: { status: VersionStatus | SolverStatus }) {
  return <span className={`status-badge status-${status.toLowerCase()}`}>{status}</span>;
}
