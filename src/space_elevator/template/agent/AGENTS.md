# AGENTS

This file defines the repository-wide authority model, workflow, and boundary rules for the local `.ci/agent` harness.

Its purpose is simple: prevent AI agents and developers from placing work in the wrong layer, reversing dependencies, leaking implementation details across boundaries, or bypassing review and progress discipline.

## Roadmap Source Of Truth

- The execution roadmap lives in `docs/progress.json`.
- `.ci/agent/progress.json` is only the vendorable starter template kept with the harness.
- Before starting any substantial implementation, refactor, or cross-boundary change, read `docs/progress.json`.
- AI agents must align proposed work with the current phase, task dependencies, and gate conditions in `docs/progress.json`.
- Do not invent a parallel roadmap in comments, commit messages, or ad hoc notes when `docs/progress.json` already covers the plan.
- If implementation reveals that the roadmap is wrong, update `docs/progress.json` first or alongside the code change so planning and execution stay synchronized.

## Execution Workflow Source Of Truth

- The detailed implementation spec for the current batch must live under `<main_worktree_root>/.tmp/`.
- Batch implementation worktrees must also live under `<main_worktree_root>/.tmp/worktrees/`.
- Specs live in the main worktree root on purpose so they survive temporary worktree deletion and remain auditable after integration, while keeping the matching batch worktree under the same local-only `.tmp/` root.
- Before starting a batch of delegated work, the Architect Agent must write an implementation spec detailed enough that a capable junior engineer could execute it without guessing.
- That spec must pass the review gate in `.ci/agent/docs/agents/spec-review.md` before worker agents start.
- If the Architect Agent inserts refactor work because the current architecture would degrade downstream implementation quality, that refactor batch or phase must also have its own `.tmp/` spec and must pass spec review before worker agents start.
- Worker Agents and Review Agents must treat the current `.tmp/` implementation spec as binding execution guidance for the active batch.

## Agent Rule Documents

- Agent-specific rule documents live under `.ci/agent/docs/agents/`.
- `.ci/agent/docs/agents/README.md` is the index.
- `.ci/agent/docs/agents/spec-review.md` defines the binding spec review gate.
- `.ci/agent/docs/agents/architect-agent.md` defines Architect Agent rules.
- `.ci/agent/docs/agents/worker-agent.md` defines Worker Agent rules.
- `.ci/agent/docs/agents/test-agent.md` defines Test Agent rules.
- `.ci/agent/docs/agents/review-agent.md` defines Review Agent rules.
- `.ci/agent/AGENTS.md` remains the source of truth for repository-wide authority, workflow, branch policy, progress policy, and boundary rules.

## PDCA Multi-Agent Workflow

This repository uses a feedback-driven PDCA workflow for substantial implementation work.

### Agent Types

- `Architect Agent`
  Owns planning, task slicing, interface freezing, agent coordination, final integration, and PR flow.
- `Worker Agent`
  Owns implementation for an assigned task or slice only.
- `Test Agent`
  A specialized Worker Agent that owns test design and test writing for an assigned batch only.
- `Review Agent`
  Owns review of any worker-claimed completion and spec review when requested by workflow.

### Required Workflow

1. The Architect Agent writes a detailed implementation spec in `<main_worktree_root>/.tmp/`.
2. Before assigning any implementation work, the Architect Agent must start a Review Agent to perform spec review under `.ci/agent/docs/agents/spec-review.md`.
3. The Architect Agent must revise the spec in response to that review before assigning any work.
4. The Architect Agent must not assign implementation work while the spec review still has blocking findings.
5. Only after the spec review has no blocking findings may the Architect Agent start worker agents, and it must explicitly tell each one its agent type and owned scope.
6. An implementation batch must be written by a Worker Agent that is not the Test Agent for that same batch.
7. If tests are needed, the Architect Agent may assign a different Test Agent for test planning or test writing, but it must explicitly state which of those scopes is being assigned.
8. The Architect Agent must not assign test-writing work until the owned implementation scope has been reported claim-complete by its responsible Worker Agent and the relevant behavior, interfaces, and acceptance criteria are stable enough to support meaningful repository-owned tests.
9. If a Test Agent is engaged before that readiness point, its scope must be limited to test planning, risk identification, or an explicit rejection decision, and it must not be asked to edit test code, fixtures, or golden data yet.
10. Before writing tests, the Test Agent must judge whether the requested tests are meaningful, proportionate, and actually protect repository-owned behavior.
11. If the proposed tests are low-value, redundant, or meaningless, the Test Agent may reject them and must explain why.
12. Worker Agents implement only the scope assigned to them and report completion claims back to the Architect Agent.
13. The Architect Agent starts or notifies a Review Agent for any claimed-complete work.
14. The Review Agent returns concrete findings, risks, and required fixes.
15. The Architect Agent sends that feedback back to the responsible Worker Agent or Test Agent.
16. The assigned agent fixes the issues and resubmits.
17. Steps 13 through 16 repeat until the Review Agent has no blocking findings.
18. Only after review passes may the Architect Agent integrate the batch and prepare the PR.

## Branch, Commit, And PR Authority

- The repository default branch is protected. Do not push directly to it.
- Do not implement, edit, or stage substantial changes in the default-branch worktree. Implementation work must happen in a dedicated `git worktree` attached to a non-default batch branch.
- Create that batch worktree under `<main_worktree_root>/.tmp/worktrees/`, for example `git worktree add <main_worktree_root>/.tmp/worktrees/<batch-id> <branch>`.
- Subagents have no authority to commit, amend commits, push branches, or create PRs.
- Only the Architect Agent may prepare the final integrated branch state and create the PR. When the active prompt explicitly instructs the Architect Agent to advance all assigned tasks through completion, the Architect Agent may also merge the PR after review passes.
- If intermediate git operations are required, subagents must leave changes in their workspace and report them back; they must not create commits themselves.
- Every implementation batch must be completed on a dedicated branch, not on the default branch.
- Every implementation batch branch must be used through its own worktree rather than by reusing the default checkout.
- The final merge into the PR branch must go through the real review path so that the final review happens on the actual integrated diff.
- After the reviewed work is merged or otherwise integrated, the corresponding temporary worktree and batch branch should be deleted promptly.
- Do not treat local completion as merged completion. A batch is only truly integrated after the final PR review path and resulting merge.

### Commit Policy

- Worker Agents: no commit authority.
- Test Agents: no commit authority.
- Review Agents: no commit authority.
- Architect Agent: may prepare integration and PR creation only after review passes, and may merge only when the active prompt explicitly grants that authority.
- Follow the repository's existing commit-title convention when one exists.
- If the repository has no established convention, use a short, specific, imperative subject and keep it within 72 characters.

## Progress Status Authority

- `docs/progress.json` is review-gated.
- Review scoring and acceptance thresholds are defined in `.ci/agent/docs/review-scoring.md`.
- Worker Agents must never mark any task or phase as `done`.
- The Architect Agent must never unilaterally mark any task or phase as `done` based on implementation alone.
- The Architect Agent may restructure future roadmap items in `docs/progress.json` when the existing task list no longer matches the required next work, but that authority does not include marking any task or phase as `done`.
- Only a Review Agent may mark a progress item complete, and only after a real review concludes that the item meets the acceptance bar.
- `ready_for_review` is allowed before completion; `done` is not.
- Completion requires a review quality score of `95` or higher.

## Global Rules

- Put code in the narrowest stable module, package, service, or layer that can own it.
- Do not cross boundaries just because it is convenient.
- Preserve the repository's current architecture before redesigning structure.
- Keep boundary types and mapping layers explicit instead of relying on hidden convenience shortcuts.
- Keep compatibility-bearing or migration-bearing data explicit; do not normalize away meaningful distinctions unless the change is deliberate and documented.
- If the repository uses delivery, domain, protocol, adapter, extension, or testing layers, keep each concern in its owning layer instead of blending them together.

## Working Principles

- Preserve behavior before redesigning structure.
- Do not make parity or compatibility claims based on surface shape alone; routing, storage, import, permissions, lifecycle, and side effects often matter.
- Prefer explicit boundary types and explicit mapping layers over hidden convenience shortcuts.

## Code Style Rules

- Keep imports or equivalent dependency declarations at the top of the file unless a compelling technical reason requires otherwise.
- If the same shape appears three or more times, extract an abstraction instead of copying it again.
- Prefer locally meaningful organization over generic helper buckets such as `utils`, `common`, or `base`.
- Prefer specific names over long or repetitive names.

## Panic And Error Rules

- Production code must not use `panic`, `.unwrap()`, or `.expect()` for routine control flow.
- Use repository-owned or boundary-owned error types where the code crosses a stable interface.
- Preserve source errors as context instead of exposing downstream implementation errors directly.
- Narrow test-only `.unwrap()` or `.expect()` usage is acceptable when it keeps the assertion clear, but do not copy that style into production paths.

## Testing Strategy

- Prefer integration-style, fixture-driven, or golden coverage for compatibility-sensitive behavior.
- Use unit tests for small pure transforms, parsers, and edge-condition checks.
- When a change affects a compatibility claim, migration claim, or public contract, update relevant tests and fixtures in the same change whenever practical.
- Do not add tests that only prove the standard library or a third-party dependency already works; test the contract that the repository owns.

Preferred testing order:

```text
integration or fixture tests
golden tests
targeted unit tests
smoke tests
```

## Dependency Rules

- Evaluate every new dependency for long-term maintenance cost, behavioral control, and whether the behavior is central to the repository.
- Do not add dependencies just to avoid writing a small amount of straightforward code.
- If the repository has a central dependency-management convention, follow it consistently across all affected manifests or lockfiles.
- Internal modules or packages should depend on each other through explicit local references rather than ad hoc duplication.

## Documentation Rules

- Document why a design exists, not only what the code already says.
- Durable PM rules live in `.ci/agent/`.
- Active specs, temporary planning material, local research, scratch copies, and dedicated batch worktrees live under `<main_worktree_root>/.tmp/`.
- `.tmp/` should be locally ignored from git tracking.
- When code changes alter roadmap assumptions or delivery sequencing, update `docs/progress.json` together with the implementation.

## Validation Workflow

Run repository-appropriate checks after code changes unless the task is explicitly documentation-only.

Preferred order:

```text
formatter
lint or static analysis
targeted tests
broader test suite when the change can affect shared behavior
```

If the repository has established commands, use them. If it does not, document what you ran and what could not be run.

## Naming Rules

- Prefer short, specific names over long descriptive names.
- Avoid names that merely repeat the surrounding module or package path.
- Use domain words first.
- Add suffixes such as `Impl`, `Manager`, `Service`, `Helper`, or `Util` only when they are strictly necessary.

## Function And Visibility Rules

- Avoid large sets of unrelated global free functions when a module, type, or owned boundary would communicate intent more clearly.
- Non-essential items must stay private.
- Do not widen visibility by default. Start private and widen only when a real boundary requires it.
- Prefer the narrowest visibility the language and repository conventions allow.

## Error Mapping Rules

- Inner layers must not know about transport-specific concerns such as HTTP status codes, CLI exit codes, protocol envelopes, or renderer-specific failures.
- Outer layers own transport-specific or delivery-specific error mapping.
- Implementation layers should preserve technical cause details for logs and diagnostics, but should not export transport-facing semantics directly.
- When an error crosses a stable boundary, expose a stable boundary-owned error type unless the module is explicitly a thin utility wrapper.

## Dependency Direction Guidance

If the repository uses a layered architecture, preserve this direction:

```text
delivery/app layers -> service/domain/protocol/adapter layers
service/use-case layers -> domain/contracts
adapter/infrastructure layers -> domain/contracts
protocol layers -> domain/service
testing layers -> anything required for verification
```

Forbidden examples in a layered repository:

- domain or core layers depending on delivery or adapter implementations
- stable interfaces depending on transport-specific packages
- production modules importing test harness utilities as runtime dependencies

## AI Placement Rules

When deciding where a change belongs:

1. Is it planning, coordination, or review workflow? Keep it in `.ci/agent/` or `.tmp/`.
2. Is it a stable product behavior? Put it in the narrowest existing production module that already owns that behavior.
3. Is it delivery-specific wiring? Keep it in the delivery or composition layer.
4. Is it infrastructure or adapter logic? Keep it behind the repository's implementation boundary.
5. Is it verification-only? Keep it in tests, fixtures, or harness code.

If a change spans multiple boundaries:

- freeze the interface first
- document owned scope explicitly in the `.tmp/` spec
- do not collapse interface and implementation into one place for convenience
