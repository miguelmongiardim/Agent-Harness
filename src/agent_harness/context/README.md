# agent_harness.context

## Purpose

`agent_harness.context` owns local document ingestion, chunking, retrieval,
context manifest assembly, and retrieval provenance. It turns configured source
files, retrieved chunks, generated handoffs, and skill guidance into manifest
records that the runtime can audit.

The package is evidence-oriented. Its outputs should explain where context came
from, why it was included or rejected, how retrieval was performed, and which
policy decisions affected the final manifest.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Context, retrieval backend, retrieval index, manifest, chunk, and provenance schema contracts. |
| `chunking.py` | Text chunking helpers and retrieved chunk records. |
| `retrieval.py` | Lexical retrieval, fake retrieval for tests, optional dense retrieval, local/server Qdrant retrievers, ingestion, and dependency availability checks. |
| `builder.py` | Builds context manifests from task sources, retrieval results, generated handoffs, and skill guidance while recording inclusion decisions. |
| `manifest.py` | Manifest-oriented helpers used by inspection and evidence paths. |
| `provenance.py` | Retrieval provenance helpers and source attribution records. |
| `qdrant_local.py` | Local Qdrant-related helpers for optional retrieval index behavior. |
| `__init__.py` | Lazily exports the public context API. |

## Context Assembly

The runtime asks this package to assemble context after loading task and policy
inputs. Source documents are chunked, retrieval backends select relevant chunks,
and generated context such as orchestration handoffs or skill guidance is added
only with policy evidence. The resulting manifest is written as run evidence and
is later consumed by inspection, MCP resources, exports, governance summaries,
and evidence pack generation.

## Boundaries

Context code should not grant authority. It can report policy decisions and
provenance, but `policy` decides whether a path, sensitivity class, skill
context item, or generated handoff may be included. Provider input construction
is also outside this package; `provider_input.py` consumes manifests after
redaction and approval rules have been applied.
