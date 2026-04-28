# Template Pack System Golden Path

This example is the V7 template-pack acceptance path for a clean local checkout.
It uses only bundled packs and local temporary targets.

## Commands

List the bundled packs:

```powershell
agent-harness template list
```

Inspect the Python library pack:

```powershell
agent-harness template show python-lib
```

Validate the pack before use:

```powershell
agent-harness template validate python-lib
```

Preview the write plan without creating files:

```powershell
agent-harness template apply python-lib --target ./scratch/python-lib --dry-run
```

Preview the generated diff without creating files:

```powershell
agent-harness template apply python-lib --target ./scratch/python-lib --preview-diff
```

Apply the pack to an empty local target:

```powershell
agent-harness template apply python-lib --target ./scratch/python-lib
```

Run release readiness, which validates bundled packs, dry-runs them,
clean-applies them to temporary release workspaces, validates generated
config/task/policy/eval examples, and confirms template application evidence:

```powershell
agent-harness release readiness
```

## Expected Evidence

The clean apply records `template_application.v1` evidence under the selected
project's `.agent-harness/template_applications/` directory. Release readiness
also writes a `template_pack_acceptance.v1` summary under
`.agent-harness/release/evidence/template-pack-acceptance.json`.

## Not Implemented

Remote catalogs, marketplace installs, cloud registries, template signing,
hooks, and script execution are not part of the V7 golden path.
