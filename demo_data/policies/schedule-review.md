# Synthetic timetable review policy

This fictional document describes the School AI demonstration workflow.

## Drafts and publication

Every successful scheduling run creates a draft version. Review its lessons
and compare it with the published version before publication. Publication is
an explicit action in the Versions screen. Publishing supersedes the previous
published version; historical lesson snapshots are retained.

## AI assistance and changes

The AI assistant may explain policies, read current school data through tools,
and request CP-SAT draft generation. It cannot publish a schedule. Conversation
memory and policy documents do not change scheduling constraints. A proposed
policy change must be implemented as validated structured requirements before
it can affect scheduling.

## Infeasible requests

If CP-SAT reports INFEASIBLE or UNKNOWN, no new timetable is fabricated or
published. Review resource availability, required sessions, room capacity,
and room types before requesting another draft.
