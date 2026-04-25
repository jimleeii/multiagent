# Orchestrator Markdown Alignment

This file aligns Orchestrator-generated markdown with [Rules.md](Rules.md).

## Scope

Apply this checklist whenever Orchestrator creates or updates markdown files in this workspace, including wiki context logs.

## Alignment Checklist

1. Heading levels increment by one only.

    - Good: `#` -> `##` -> `###`
    - Avoid: `#` -> `###`

2. Use one heading style consistently.

    - Prefer ATX headings (`#`, `##`, `###`).
    - Do not mix setext (`===`, `---`) with ATX in the same file.

3. Use one unordered list marker consistently.

    - Prefer dash marker (`-`) across the file.

4. Keep list indentation consistent.

    - Same nesting level must align to the same column.

5. Use 2-space indentation for nested unordered lists.

6. Avoid trailing spaces.

    - No unnecessary spaces at line ends.

## Writing Profile for Orchestrator

Use this default profile when generating markdown:

- Heading style: ATX
- Unordered list marker: dash (`-`)
- Nested unordered list indentation: 2 spaces
- No trailing spaces

## Quick Self-Check Before Save

- Are heading levels sequential?
- Is heading style consistent?
- Are unordered lists using one marker?
- Is list indentation consistent and 2-space nested?
- Are trailing spaces removed?

## Notes

If future rule settings in [Rules.md](Rules.md) change, update this alignment file and Orchestrator instructions together.
