# Orchestrator Wiki Home

## Purpose

This wiki tracks subagent behavior, recurring patterns, and orchestrator self-improvement actions.

## Pages

- [[Project-Context-Log]]
- [[Behavior-Log]]
- [[Behavior-Patterns]]
- [[Learning-Backlog]]
- [[Runbook]]

## Operating Cycle

0. Read [[Project-Context-Log]] at day start and capture a short Today Context summary.
1. Dispatch subagent and evaluate output.
2. Append observation to [[Behavior-Log]].
3. Extract recurring issues to [[Behavior-Patterns]].
4. Add actionable fixes to [[Learning-Backlog]].
5. Apply one safe policy improvement and document in [[Runbook]].
6. Append short execution context to [[Project-Context-Log]].

## Cadence

- Once per day before first task: review [[Project-Context-Log]], [[Learning-Backlog]], and latest [[Runbook]] checkpoint.
- Every 10 new observations in [[Behavior-Log]]: run pattern compaction in [[Behavior-Patterns]].
- Every 7 days: triage [[Learning-Backlog]] priorities and statuses.
- After each triage: add a checkpoint in [[Runbook]] with what changed.
