# Agents

Agent layer components:
- `router.py`: picks database and coarse plan.
- `schema.py`: AutoLink-style schema linker with iterative actions.
- `sql_generator.py`: produces SQL candidates from linked schema.
- `verifier.py`: probes SQL and emits final decision.

Agents only read/write portions of `QueryContext` relevant to their role.
