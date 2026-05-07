# agent_harness.operator.static

## Purpose

`agent_harness.operator.static` stores the packaged browser assets for the local
operator UI. The Python package marker lets these files ship as package data and
be served by `agent_harness.operator.app`.

This directory contains frontend assets only. API behavior, authentication,
artifact loading, approval decisions, and safety checks belong in
`agent_harness.operator.app`.

## Files

| File | Role |
| --- | --- |
| `index.html` | Static document shell for the local operator surface. |
| `app.css` | UI layout and styling for run, approval, governance, and evidence views. |
| `app.js` | Browser-side fetch/render logic for the operator API. |
| `__init__.py` | Package marker for static asset discovery. |

## Boundaries

Keep these assets self-contained and local. Do not add remote assets, analytics,
browser persistence of sensitive evidence, or direct filesystem access. All data
should come from token-protected local API routes.
