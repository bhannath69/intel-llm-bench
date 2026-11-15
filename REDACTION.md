# Redaction

Logs and configs here are copied from internal test runs by a script, not by hand. The script selects
the relevant lines, rewrites environment-specific details, and refuses to export if anything from the
categories below remains anywhere in the repo.

## What is changed or removed

| Category | Treatment |
|---|---|
| Internal hostnames | Replaced with the public rig name (for example `xeon-676x-4x-b70`). |
| Local filesystem paths | Model cache paths become `<hf-cache>/<org>/<model>@<revision>`; other host paths become generic container paths such as `/models/...`. |
| Private network addresses | Removed or replaced with `<container-ip>`. Loopback (`127.0.0.1`) is kept. |
| Internal run codes and tracking ids | Replaced with neutral wording. |
| Credentials, tokens, account references | Never exported. |
| Unrelated operational notes | Not exported; only lines that support a published number or flag are kept. |

## What is never changed

Measured numbers, timestamps, version strings, commit hashes, model revisions, and the order of log lines.
An excerpt file starts with a header saying which lines of the original it contains, for example
`# excerpt: server.log, 12 of 1840 lines (lines 6,10,19-20)`.

PCI addresses of the GPUs are kept: they are generic platform details and they show which slot each card
used.
