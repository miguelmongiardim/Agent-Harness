# Evaluations

V0 evals are designed to catch workflow regressions rather than benchmark model
quality.

The bundled eval suite focuses on:

- schema strictness
- policy precedence and path sandboxing
- deterministic retrieval fallback
- mock model integrity
- approval-bound patch application
- stable run artifacts under fixed seeds

The mock model must consume real task specs, context manifest content, and tool
observations. Tests intentionally verify that changing observations changes
proposed behavior and that task ids alone are insufficient to drive actions.
