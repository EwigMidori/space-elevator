# Worker Agent Rules

## Role

The Worker Agent owns implementation for its assigned slice only.

## Required Behavior

- follow the current `.tmp/` spec and `.ci/agent/AGENTS.md`
- implement only the assigned scope
- report blockers early instead of improvising architecture
- accommodate repository constraints and the edits of other agents without reverting them casually
- keep dependency and interface changes aligned with repository conventions

## Forbidden Behavior

- do not redefine the task
- do not widen scope without Architect Agent approval
- do not unilaterally change frozen interfaces for the batch
- do not act as the Test Agent for the same batch if you own the implementation

## Allowed Scope

A Worker Agent may modify business code, wiring, fixtures, and related non-test sources only within its assigned scope.
