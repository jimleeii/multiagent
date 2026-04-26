# Orchestrator Wiki Home

## Purpose

This wiki tracks subagent behavior, recurring patterns, and orchestrator self-improvement actions.

## Pages

- [[Project-Context-Log]]
- [[Behavior-Log]]
- [[Skill-Usage-Log]]
- [[Behavior-Patterns]]
- [[Learning-Backlog]]
- [[Runbook]]

## Operating Cycle

0. Read [[Project-Context-Log]] at day start and capture a short Today Context summary.
1. Dispatch subagent and evaluate output.
2. Append observation to [[Behavior-Log]].
3. Append skills used and reuse notes to [[Skill-Usage-Log]].
4. Extract recurring issues to [[Behavior-Patterns]].
5. Add actionable fixes to [[Learning-Backlog]].
6. Apply one safe policy improvement and document in [[Runbook]].
7. Append short execution context to [[Project-Context-Log]].

## Cadence

- Once per day before first task: review [[Project-Context-Log]], [[Learning-Backlog]], and latest [[Runbook]] checkpoint.
- Every 10 new observations in [[Behavior-Log]]: run pattern compaction in [[Behavior-Patterns]].
- Every 15 new entries in [[Skill-Usage-Log]]: summarize high-value skill combinations in [[Behavior-Patterns]].
- Every 7 days: triage [[Learning-Backlog]] priorities and statuses.
- After each triage: add a checkpoint in [[Runbook]] with what changed.
