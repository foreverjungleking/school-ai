import type { Availability, SchoolData } from "../types";

const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const shortTime = (value: string) => value.slice(0, 5);

function AvailabilityList({ items }: { items: Availability[] }) {
  if (!items.length) return <span className="muted">Unrestricted</span>;
  return <div className="availability-list">{items.map((item) => (
    <span className={item.available ? "window allowed" : "window blocked"} key={item.id}>
      {days[item.weekday]} {shortTime(item.start_time)}–{shortTime(item.end_time)}
    </span>
  ))}</div>;
}

export function SchoolDataTables({ data }: { data: SchoolData }) {
  const teacherName = new Map(data.teachers.map((item) => [item.id, item.name]));
  const groupName = new Map(data.groups.map((item) => [item.id, item.name]));
  return (
    <>
      <header className="page-header"><div><p className="eyebrow">School resources</p><h1>The inputs behind every schedule.</h1><p>Read-only synthetic data supplied to the CP-SAT engine through application services.</p></div></header>
      <section className="data-section panel"><div className="panel-heading"><div><h2>Teachers</h2><p>{data.teachers.length} educators and their availability</p></div></div><div className="table-wrap"><table><thead><tr><th>Name</th><th>Availability</th></tr></thead><tbody>{data.teachers.map((teacher) => <tr key={teacher.id}><td><strong>{teacher.name}</strong><small>ID {teacher.id}</small></td><td><AvailabilityList items={teacher.availability} /></td></tr>)}</tbody></table></div></section>
      <section className="data-section panel"><div className="panel-heading"><div><h2>Rooms</h2><p>Capacity, type, and operating windows</p></div></div><div className="table-wrap"><table><thead><tr><th>Room</th><th>Type</th><th>Capacity</th><th>Availability</th></tr></thead><tbody>{data.rooms.map((room) => <tr key={room.id}><td><strong>{room.name}</strong></td><td>{room.room_type}</td><td>{room.capacity}</td><td><AvailabilityList items={room.availability} /></td></tr>)}</tbody></table></div></section>
      <div className="two-column-data">
        <section className="data-section panel"><div className="panel-heading"><div><h2>Student groups</h2><p>Classes included in scheduling</p></div></div><div className="table-wrap"><table><thead><tr><th>Group</th><th>Students</th></tr></thead><tbody>{data.groups.map((group) => <tr key={group.id}><td><strong>{group.name}</strong></td><td>{group.size}</td></tr>)}</tbody></table></div></section>
        <section className="data-section panel"><div className="panel-heading"><div><h2>Activities</h2><p>Weekly lesson requirements</p></div></div><div className="table-wrap"><table><thead><tr><th>Subject</th><th>Class</th><th>Teacher</th><th>Sessions</th><th>Room type</th></tr></thead><tbody>{data.activities.map((activity) => <tr key={activity.id}><td><strong>{activity.name}</strong><small>{activity.duration_minutes} min</small></td><td>{groupName.get(activity.student_group_id)}</td><td>{teacherName.get(activity.teacher_id)}</td><td>{activity.sessions_per_week}</td><td>{activity.required_room_type}</td></tr>)}</tbody></table></div></section>
      </div>
    </>
  );
}
