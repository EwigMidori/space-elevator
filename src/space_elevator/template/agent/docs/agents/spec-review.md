# Spec Review Rules

## Purpose

This document defines the required review gate for an implementation spec before any Worker Agent starts.

The goal is simple: prevent work from starting on a vague `.tmp/` spec that forces downstream agents to guess behavior, boundaries, or acceptance criteria.

## When Spec Review Is Required

Spec review is required before starting any Worker Agent for a new batch or materially revised batch.

If the implementation spec changes in a way that affects scope, interfaces, boundaries, acceptance criteria, or task slicing, the Architect Agent must update the spec and run spec review again before assigning new implementation work under that changed scope.

## Reviewer

- The spec review must be performed by a `Review Agent`.
- It is a real review, not a rubber-stamp acknowledgment.
- It must be framed as spec review, not as implementation review or completion confirmation.

## Minimum Spec Content

The `.tmp/` implementation spec must be detailed enough that a capable junior engineer could execute it without guessing.

At minimum, the spec must make all of the following explicit:

- batch scope and non-goals
- relevant roadmap task IDs and phase gates
- owned modules, files, packages, services, or subsystems
- frozen interfaces, inputs, outputs, and boundary types
- task slicing and owned scope for each downstream agent
- important control flow, state changes, and error paths
- edge cases, negative cases, and compatibility-sensitive traps
- acceptance criteria and validation plan
- constraints on widening scope, redesigning interfaces, or improvising architecture

## What The Review Must Check

The spec review must look for:

- missing edge cases
- unclear boundaries
- unfrozen interfaces
- vague or non-verifiable acceptance criteria
- weak task slicing that would cause overlapping ownership
- omissions that would force a Worker Agent to guess design intent
- contradictions with `.ci/agent/AGENTS.md` or `docs/progress.json`

## Review Outcome

- If the review finds blocking gaps, the Architect Agent must revise the spec before assigning any Worker Agent.
- If the review has no blocking findings, the Architect Agent may proceed with worker assignment under that reviewed spec.
