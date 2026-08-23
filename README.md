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
- pytest coverage using an in-memory SQLite database

API endpoints and AI integrations are planned but are not yet implemented.
