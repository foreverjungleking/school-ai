import { useState } from "react";
import type { Schedule, ScheduleComparison, ScheduleVersion, SchoolData } from "../types";
import { StatusBadge } from "./StatusBadge";
import { VersionComparison } from "./VersionComparison";

export function Versions({
  schedule,
  versions,
  comparison,
  publishingId,
  comparing,
  onSelect,
  onPublish,
  onCompare,
  data,
}: {
  schedule: Schedule | null;
  versions: ScheduleVersion[];
  comparison: ScheduleComparison | null;
  publishingId: number | null;
  comparing: boolean;
  onSelect: (version: ScheduleVersion) => void;
  onPublish: (version: ScheduleVersion) => void;
  onCompare: (fromId: number, toId: number) => void;
  data: SchoolData;
}) {
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  return (
    <>
      <header className="page-header"><div><p className="eyebrow">Schedule history</p><h1>{schedule?.name ?? "Versions"}</h1><p>Every solver result is a separate snapshot. Publishing never edits an existing timetable.</p></div></header>
      <section className="panel versions-panel">
        <div className="panel-heading"><div><h2>Version timeline</h2><p>{versions.length} stored snapshots</p></div></div>
        {!versions.length ? <div className="empty-state"><strong>No versions yet</strong><p>Generate a draft from Overview to start the history.</p></div> : <div className="version-list">{[...versions].reverse().map((version) => (
          <article className="version-row" key={version.id}>
            <button className="version-main" onClick={() => onSelect(version)}><span className="version-number">v{version.version_number}</span><div><strong>{new Date(version.created_at).toLocaleString()}</strong><small>{version.lessons.length} lessons · {version.solver_status} · {version.solve_duration_seconds.toFixed(3)}s</small></div></button>
            <StatusBadge status={version.status} />
            {version.status === "DRAFT" && <button className="publish-action" disabled={publishingId !== null} onClick={() => onPublish(version)}>{publishingId === version.id ? "Publishing…" : "Publish draft"}</button>}
          </article>
        ))}</div>}
      </section>
      <section className="panel comparison-panel">
        <div className="panel-heading"><div><h2>Compare versions</h2><p>Change classification comes directly from the application service.</p></div></div>
        <div className="compare-controls"><label>From<select aria-label="Compare from version" value={fromId} onChange={(event) => setFromId(event.target.value)}><option value="">Select version</option>{versions.map((version) => <option value={version.id} key={version.id}>Version {version.version_number} · {version.status}</option>)}</select></label><span aria-hidden="true">→</span><label>To<select aria-label="Compare to version" value={toId} onChange={(event) => setToId(event.target.value)}><option value="">Select version</option>{versions.map((version) => <option value={version.id} key={version.id}>Version {version.version_number} · {version.status}</option>)}</select></label><button className="secondary-action" disabled={!fromId || !toId || fromId === toId || comparing} onClick={() => onCompare(Number(fromId), Number(toId))}>{comparing ? "Comparing…" : "Compare"}</button></div>
        <VersionComparison comparison={comparison} data={data} />
      </section>
    </>
  );
}
