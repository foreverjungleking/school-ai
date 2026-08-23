import type { ScheduleComparison, SchoolData, ScheduledLesson } from "../types";

function LessonLine({ lesson, data }: { lesson: ScheduledLesson; data: SchoolData }) {
  const activity = data.activities.find((item) => item.id === lesson.activity_id)?.name ?? `Activity ${lesson.activity_id}`;
  const room = data.rooms.find((item) => item.id === lesson.room_id)?.name ?? `Room ${lesson.room_id}`;
  return <span><strong>{activity}</strong> · Day {lesson.weekday + 1}, {lesson.start_time.slice(0, 5)} · {room}</span>;
}

export function VersionComparison({ comparison, data }: { comparison: ScheduleComparison | null; data: SchoolData }) {
  if (!comparison) return <div className="empty-state compact"><strong>No comparison selected</strong><p>Choose two versions to ask the backend what changed.</p></div>;
  return (
    <div className="comparison-results" aria-label="Version comparison results">
      <div className="comparison-summary">
        <span><strong>{comparison.unchanged.length}</strong> unchanged</span>
        <span className="changed"><strong>{comparison.changed.length}</strong> moved</span>
        <span className="added"><strong>{comparison.added.length}</strong> added</span>
        <span className="removed"><strong>{comparison.removed.length}</strong> removed</span>
      </div>
      {comparison.changed.map((change) => <article className="change-row changed" key={`changed-${change.after.activity_id}-${change.after.session_index}`}><span className="change-label">Moved</span><div><LessonLine lesson={change.before} data={data} /><span className="change-arrow">→</span><LessonLine lesson={change.after} data={data} /></div></article>)}
      {comparison.added.map((lesson) => <article className="change-row added" key={`added-${lesson.id}`}><span className="change-label">Added</span><LessonLine lesson={lesson} data={data} /></article>)}
      {comparison.removed.map((lesson) => <article className="change-row removed" key={`removed-${lesson.id}`}><span className="change-label">Removed</span><LessonLine lesson={lesson} data={data} /></article>)}
      {comparison.unchanged.length > 0 && <details><summary>{comparison.unchanged.length} unchanged lessons</summary><div className="unchanged-list">{comparison.unchanged.map((lesson) => <LessonLine lesson={lesson} data={data} key={`same-${lesson.id}`} />)}</div></details>}
    </div>
  );
}
