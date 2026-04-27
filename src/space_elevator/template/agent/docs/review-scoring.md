# Review Scoring

Use this rubric when a Review Agent decides whether a batch is complete enough to mark `done`.

## Threshold

- `95-100`: complete enough to mark `done`
- `80-94`: substantial progress, but return findings and keep the item out of `done`
- `<80`: incomplete or unsafe, return blocking findings

## Scoring Dimensions

- `Correctness` (45)
  The implementation matches the spec and intended behavior, including edge cases.
- `Regression Safety` (20)
  The change avoids obvious breakage, preserves existing contracts, and handles migration or compatibility risks appropriately.
- `Boundary Discipline` (15)
  The work respects repository boundaries, avoids leaking implementation details, and keeps ownership clear.
- `Test Signal` (10)
  Tests, if present, protect a real repository-owned contract instead of adding weak or redundant coverage.
- `Operability And Documentation` (10)
  Validation, docs, follow-up notes, or roadmap updates are sufficient for the type of change made.

## Required Output

When returning findings:

- cite the concrete issue
- explain why it matters
- describe the required fix or missing evidence

When marking work complete:

- state the score
- state which roadmap item is eligible for `done`
- mention any residual non-blocking risk explicitly
