<!-- pragmatic-developer:start -->
# Pragmatic Developer Guidance

Use the `pragmatic-developer` skill for domain modeling, clean code, TDD, refactoring, design patterns, algorithmic tradeoffs, and project preference tracking.

Before changing design direction:

- Read `.codex/project-profile.md`.
- Read relevant specs in `.codex/specs` before changing behavior.
- For an existing codebase, infer and follow observed architecture, naming, test style, and design patterns before suggesting alternatives.
- For existing projects, fill spec placeholders gradually from code, tests, docs, and user confirmation. Do not invent behavior.
- For greenfield work, record provisional choices in `.codex/project-profile.md` and update them as the project matures.
- When the user chooses between design options, update `.codex/project-profile.md` with the decision, rationale, and scope.
- When expected behavior, acceptance criteria, domain rules, API contracts, data behavior, or test proof changes, update the relevant spec in `.codex/specs`.
- Keep code smell fixes compatible with the current repo first; present larger design alternatives with tradeoffs.

This guidance is intended for Claude.
<!-- pragmatic-developer:end -->
