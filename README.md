# School AI

School AI is a public-demo school activity and timetable management system built
with synthetic data.

The current implementation provides the initial domain and persistence layer:

- SQLAlchemy 2.x models for teachers, student groups, rooms, activities, and
  teacher/room availability
- Pydantic schemas for validating and serializing those entities
- PostgreSQL configuration through `DATABASE_URL`
- pytest coverage using an in-memory SQLite database

Scheduling, API endpoints, and AI integrations are planned but are not yet
implemented.
