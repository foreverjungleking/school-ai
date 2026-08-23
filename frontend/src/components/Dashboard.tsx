import type { Schedule, ScheduleVersion, SchoolData } from "../types";
import { StatusBadge } from "./StatusBadge";

export function Dashboard({
  data,
  schedule,
  published,
  latestDraft,
  generating,
  onGenerate,
  onOpenTimetable,
}: {
  data: SchoolData;
  schedule: Schedule | null;
  published: ScheduleVersion | null;
  latestDraft: ScheduleVersion | null;
  generating: boolean;
  onGenerate: () => void;
  onOpenTimetable: () => void;
}) {
  const stats = [
    ["Teachers", data.teachers.length, "Available educators"],
    ["Rooms", data.rooms.length, "Teaching spaces"],
    ["Student groups", data.groups.length, "Classes to schedule"],
    ["Activities", data.activities.length, "Weekly subjects"],
  ] as const;
  return (
    <>
      <header className="page-header hero-header">
        <div>
          <p className="eyebrow">Scheduling workspace</p>
          <h1>Make the school week fit.</h1>
          <p>Generate a constraint-safe timetable, inspect every lesson, and publish only when the draft is ready.</p>
        </div>
        <button className="primary-action" disabled={generating} onClick={onGenerate}>
          {generating ? <><span className="spinner" /> Solving timetable…</> : "Generate new draft"}
        </button>
      </header>
      <section className="stat-grid" aria-label="School summary">
        {stats.map(([label, value, hint]) => (
          <article className="stat-card" key={label}>
            <span>{label}</span><strong>{value}</strong><small>{hint}</small>
          </article>
        ))}
      </section>
      <section className="dashboard-grid">
        <article className="panel schedule-overview">
          <div className="panel-heading"><div><p className="eyebrow">Current timetable</p><h2>{schedule?.name ?? "No schedule yet"}</h2></div></div>
          {published ? (
            <div className="version-callout">
              <div><StatusBadge status={published.status} /><h3>Version {published.version_number}</h3><p>{published.lessons.length} scheduled lessons</p></div>
              <button className="secondary-action" onClick={onOpenTimetable}>View timetable</button>
            </div>
          ) : (
            <div className="empty-state compact"><strong>No published timetable</strong><p>Generate a draft, review the result, then publish deliberately.</p></div>
          )}
        </article>
        <article className="panel draft-overview">
          <div className="panel-heading"><div><p className="eyebrow">Latest work</p><h2>Draft status</h2></div></div>
          {latestDraft ? (
            <div className="draft-summary"><StatusBadge status={latestDraft.status} /><strong>Version {latestDraft.version_number}</strong><p>{latestDraft.solver_status} in {latestDraft.solve_duration_seconds.toFixed(3)}s</p><small>{latestDraft.lessons.length} lessons ready to review</small></div>
          ) : <div className="empty-state compact"><strong>No active draft</strong><p>Your next solver run will create one.</p></div>}
        </article>
      </section>
      <section className="workflow-strip" aria-label="Demo workflow">
        {[
          ["01", "Review resources"], ["02", "Generate draft"], ["03", "Compare changes"], ["04", "Publish explicitly"],
        ].map(([number, label]) => <div key={number}><span>{number}</span><strong>{label}</strong></div>)}
      </section>
    </>
  );
}
