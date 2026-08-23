import { useMemo, useState } from "react";
import type { ScheduleVersion, SchoolData } from "../types";
import { StatusBadge } from "./StatusBadge";

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const hours = Array.from({ length: 8 }, (_, index) => index + 8);
const shortTime = (value: string) => value.slice(0, 5);

export function Timetable({ version, data }: { version: ScheduleVersion | null; data: SchoolData }) {
  const [filterType, setFilterType] = useState<"group" | "teacher" | "room">("group");
  const [filterId, setFilterId] = useState("all");
  const options = filterType === "group" ? data.groups : filterType === "teacher" ? data.teachers : data.rooms;
  const activities = useMemo(() => new Map(data.activities.map((item) => [item.id, item])), [data.activities]);
  const teachers = useMemo(() => new Map(data.teachers.map((item) => [item.id, item.name])), [data.teachers]);
  const groups = useMemo(() => new Map(data.groups.map((item) => [item.id, item.name])), [data.groups]);
  const rooms = useMemo(() => new Map(data.rooms.map((item) => [item.id, item.name])), [data.rooms]);
  const lessons = (version?.lessons ?? []).filter((lesson) => {
    if (filterId === "all") return true;
    const id = Number(filterId);
    return filterType === "group" ? lesson.student_group_id === id : filterType === "teacher" ? lesson.teacher_id === id : lesson.room_id === id;
  });
  return (
    <>
      <header className="page-header"><div><p className="eyebrow">Weekly timetable</p><h1>{version ? `Version ${version.version_number}` : "No timetable selected"}</h1><p>{version ? <><StatusBadge status={version.status} /> {lessons.length} lessons in this view</> : "Generate a draft to see the CP-SAT result."}</p></div></header>
      <section className="panel timetable-panel">
        <div className="filter-bar"><label>View by<select aria-label="Filter type" value={filterType} onChange={(event) => { setFilterType(event.target.value as typeof filterType); setFilterId("all"); }}><option value="group">Student group</option><option value="teacher">Teacher</option><option value="room">Room</option></select></label><label>Resource<select aria-label="Filter resource" value={filterId} onChange={(event) => setFilterId(event.target.value)}><option value="all">All resources</option>{options.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
        {!version ? <div className="empty-state"><strong>Your timetable will appear here.</strong><p>Return to Overview and generate the first draft.</p></div> : (
          <div className="calendar" aria-label="Weekly timetable">
            <div className="calendar-corner">Time</div>{days.map((day) => <div className="day-heading" key={day}>{day}</div>)}
            {hours.flatMap((hour) => [
              <div className="time-label" key={`time-${hour}`}>{String(hour).padStart(2, "0")}:00</div>,
              ...days.map((_, weekday) => {
                const cellLessons = lessons.filter((lesson) => lesson.weekday === weekday && Number(lesson.start_time.slice(0, 2)) === hour);
                return <div className="calendar-cell" key={`${weekday}-${hour}`}>{cellLessons.map((lesson) => { const activity = activities.get(lesson.activity_id); return <article className={`lesson-card subject-${lesson.activity_id % 5}`} key={lesson.id}><strong>{activity?.name ?? `Activity ${lesson.activity_id}`}</strong><span>{shortTime(lesson.start_time)}–{shortTime(lesson.end_time)}</span><small>{groups.get(lesson.student_group_id)} · {rooms.get(lesson.room_id)}</small><small>{teachers.get(lesson.teacher_id)}</small></article>; })}</div>;
              }),
            ])}
          </div>
        )}
      </section>
    </>
  );
}
