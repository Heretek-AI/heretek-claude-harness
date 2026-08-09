# ADR Lifecycle Standard

## Decision

All ADRs (`catalog/reviews/*.md`) use a **two-state Verdict**:

```
## Verdict

- [ ] Approved
- [ ] Rejected

Reason: ...
```

No intermediate "Proposed" state. ADRs begin life with the `status: pending` frontmatter field and remain pending until an author checks one of the two checkboxes.

## Rationale

- 36 of 37 existing ADRs already use two-state.
- The template (`catalog/reviews/0000-template.md`) defines two-state.
- "Proposed" adds ceremony without signal -- the frontmatter `status: pending` already conveys "not yet decided."

## What changed

`observability-sub-spec-1.md` was the only ADR using three-state (`- [x] Proposed`). Its Verdict was reverted to the standard two-state form. No other ADRs or the template required modification.

## Applicability

Future ADR authors: follow `catalog/reviews/0000-template.md` Verdict section verbatim. Do not add intermediate lifecycle states.
