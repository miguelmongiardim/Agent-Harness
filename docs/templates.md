# Template Catalog

## Current Capabilities

The bundled template catalog is local and packaged with the Python package.
`agent-harness template list` and `agent-harness template show <id>` read
registry metadata and public template manifests.

`template.v2` is the current public template manifest. It records:

- minimum Agent Harness version
- required template capabilities
- generated schema versions
- provider/profile requirements
- policy requirements
- retrieval assumptions
- eval or demo metadata

The bundled V2 Python trio is:

- `python-lib`
- `cli-tool`
- `fastapi-service`

Bundled templates can be validated with:

```powershell
agent-harness template validate --all
```

Validation lists, loads, and applies each bundled template into a clean local
validation workspace. The command records
`.agent-harness/release/evidence/template-validation.json` for release
readiness.

Clean empty-destination scaffolding does not require approval. A normal apply
to a new destination completes immediately and records the template id and
version in workspace metadata.

Approval remains required for a non-empty destination, `--force` overwrite
planning, or higher-risk mutations. Incompatible required capabilities are
rejected before write planning.

`template.v1` bundles remain readable through compatibility loading.

## Roadmap

External catalogs, remote template discovery, and non-Python template expansion
are not part of the current V2 release.
