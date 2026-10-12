# ADR 0003: Project license is Apache-2.0 (ARCHITECTURE.md §40)

Status: accepted. Supersedes the unrecorded `LICENSE` change in commit
`7b16dce` (AGPL-3.0 text).

`ARCHITECTURE.md` §40 decides that original project code is Apache-2.0 and that
the process boundary with AGPL-3.0 KOReader is what keeps Shell/Core out of
AGPL's copyleft. The repository `LICENSE` file had been replaced with the
AGPL-3.0 text without an ADR, while `pyproject.toml` and
`packages/ereader-core/package.json` continued to declare Apache-2.0.

The `LICENSE` file is restored to Apache-2.0 so that the file, the package
metadata and §40 agree. KOReader (and any patches to it) stay AGPL-3.0.

If the maintainer deliberately wants AGPL-3.0 for the whole project, §40 must
be amended first and the metadata changed in the same commit; do not leave the
three sources disagreeing.
