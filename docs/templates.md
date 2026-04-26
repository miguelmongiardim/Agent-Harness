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

Template application remains approval-bound. Incompatible required
capabilities are rejected before write planning, and successful apply records
template id and version in workspace metadata.

`template.v1` bundles remain readable through compatibility loading.

## Roadmap

External catalogs, remote template discovery, and non-Python template expansion
are not part of the current V2 release.
