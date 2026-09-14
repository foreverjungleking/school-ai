# Synthetic school scenario

The installed `school_ai.demo_seed` command defines and loads this fictional
lower-secondary school. It represents a useful scheduling test, not an official
curriculum or a real school's staffing model.

- Four classes of 22–28 students, eight subject teachers, seven rooms.
- Each class has 25 one-hour lessons per week: Mathematics 5, English 5,
  Science 4, History 3, Physical Education 2, Music 2, Computing 2, Visual Arts 2.
- Candidate teaching hours are 08:00–12:00 and 13:00–15:00, Monday–Friday.
  Teacher and room availability protect lunch and the end of the school day,
  including when a caller submits the older 08:00–16:00 candidate grid.
- Four general classrooms, one laboratory, one music studio, and one sports
  hall create both parallel teaching capacity and shared specialist resources.
- CP-SAT prefers equal daily teaching minutes per class and fewer same-subject
  repeats on a day. These preferences are soft, so restricted datasets can
  still be feasible. Neither breaks nor resource conflicts are soft.

The previous smoke-test dataset contained only 16 lessons across the whole
school (3–5 per class per week), with unrestricted weekday teaching windows.
A feasibility-only solver could place all 16 on Monday.

For an empty migrated database, run `python -m school_ai.demo_seed`. For an
existing deployment containing the known synthetic demo, explicitly run
`python -m school_ai.demo_seed --expand`. This adds missing resources and
subjects and updates the demo's curriculum, staffing assignments, music room
capacity, and availability. It preserves existing activity IDs and all stored
schedule versions and lesson rows. It refuses unknown resource names and
unknown/duplicate subjects; it is not a general importer for other schools.
Normal seeding still leaves existing data alone. Repeating expansion makes no
further changes.

After expansion, generate a new draft and review it before publication. Old
versions retain their old assignments. Expansion is an explicit demo-data
operation, never an automatic startup or migration step.

Remaining simplifications include one teacher and one group per activity,
uniform one-hour lessons, and no assembly, registration, short recess,
co-teaching, split classes, or teacher-specific part-time windows. Those require
separate structured requirements and tests before representing a real school.
