# Test Agent Handbook

This handbook defines when a Test Agent should write tests, reject tests, or defer test work.

## Decision Gate

Write tests only when all of the following are true:

- the owned behavior already exists or is stable enough to test
- the test protects a repository-owned contract
- the assertion meaningfully detects a regression
- the maintenance cost is proportionate to the risk covered

Reject or defer the test request when any of the following are true:

- the implementation is visibly incomplete
- the contract is not yet frozen
- the proposed test only replays framework behavior
- the assertion is too weak to prove anything important
- the request exists only because "there should probably be a test"

## Minimum Assertion Bar

- Prefer assertions on externally visible behavior, contract outputs, state transitions, or user-observable failure modes.
- Avoid weak assertions such as only checking that an error happened without verifying which contract failed.
- Prefer one high-signal test over many repetitive shallow tests.

## Allowed Edit Scope

The Test Agent may modify:

- test files
- fixtures
- golden files
- test-only harness code
- doc-comment examples whose sole purpose is executable documentation

The Test Agent must not modify production behavior under the pretext of adding tests.
