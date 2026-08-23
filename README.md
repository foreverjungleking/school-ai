# School AI

School AI is a public-demo school activity and timetable management system built
with synthetic data.

The current implementation provides:

- SQLAlchemy 2.x models for teachers, student groups, rooms, activities, and
  teacher/room availability
- Pydantic schemas for validating and serializing those entities
- PostgreSQL configuration through `DATABASE_URL`
- A deterministic, database-independent OR-Tools CP-SAT scheduling engine with
  hard constraints for availability, resource conflicts, required sessions, and
  room suitability
- Application services and focused repositories that translate persisted school
  data into solver DTOs and persist successful results as versioned schedules
- pytest coverage using an in-memory SQLite database

API endpoints and AI integrations are planned but are not yet implemented.

## Schedule lifecycle

A `Schedule` is the stable identity of a timetable. Every successful CP-SAT run
creates a new `ScheduleVersion` in `DRAFT` status and stores its assignments as
`ScheduledLesson` rows. Existing versions are not overwritten. Solver outcomes
that are `INFEASIBLE`, `UNKNOWN`, or contain no assignments do not create a
version or fabricated lessons; their diagnostic metadata is returned by the
application service.

Publishing is a separate explicit service operation. Publishing a draft marks
it `PUBLISHED` and marks the prior published version `SUPERSEDED`, ensuring at
most one current publication per schedule. Further changes require generating a
new draft rather than modifying a published lesson snapshot in place.

The project does not yet use a migration framework. Tests and current database
initialization use SQLAlchemy's `Base.metadata.create_all()`; production schema
migrations remain a future infrastructure milestone.
