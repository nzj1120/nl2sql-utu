# Core

Core runtime primitives:
- `context.py`: `QueryContext` definition and helpers.
- `pipeline.py`: Orchestrator that chains Router → Schema → SQL Generator → Verifier.

These modules are intentionally framework-agnostic to plug into API/UI layers.
