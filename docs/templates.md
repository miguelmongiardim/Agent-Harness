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

The bundled v1.4.0 pack set is:

- `python-lib`
- `cli-tool`
- `fastapi-service`
- `provider-audit`
- `retrieval-quality`

Bundled templates can be validated with:

```powershell
agent-harness template validate --all
```

Validation lists, loads, and applies each bundled template into a clean local
validation workspace. The command records
`.agent-harness/release/evidence/template-validation.json` for release
readiness.

Clean empty-destination scaffolding does not require approval. A normal apply
to a new destination completes immediately, writes declared template files only,
persists `template_application.v1` evidence under
`.agent-harness/template_applications/`, and records the template id, version,
target, and evidence path in workspace metadata.

Every bundled pack includes `template.v2.toml`, README content, demo metadata,
and generated JSON examples for config, policy, task, and eval schemas.
Template validation and clean apply exercise those examples as local files; no
remote catalog or hook execution is involved.

Approval remains required for a non-empty destination, `--force` overwrite
planning, or higher-risk mutations. Incompatible required capabilities are
rejected before write planning.

`template.v1` bundles remain readable through compatibility loading.

## Roadmap

External catalogs, remote template discovery, and organization-wide template
distribution are not part of the current release.

The planned v1.4.0 Template Pack System is documented in
[template-pack-system.md](template-pack-system.md). v1.4.0 keeps template packs
local-first, explicit, and inspectable while adding pack manifests, dry-run
planning, preview diffs, clean-apply evidence, and release-readiness gates.
