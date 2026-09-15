# Contributing to MCP-Pi

MCP-Pi is security-sensitive and intentionally small. Contributions should preserve its KISS, fail-closed and low-resource character.

## Branches

```text
main      known-good release line
develop   integrated validated development
feature/* or fix/*  isolated work when useful
```

Do not force-push release history or move existing tags.

## Development flow

1. Start from `develop`.
2. Make the smallest coherent change.
3. Add/update regression tests.
4. Run applicable gates.
5. Update CURRENT docs when behavior/contracts changed.
6. Run the documentation audit and `git diff --check`.
7. Commit/push and require CI before hardware promotion.

Full release gate:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
cd mcp-adapter && go test ./...
cd ..
node tests/test_app_js.mjs
cd tailwind && npm run build
cd ..
python scripts/audit-docs.py
git diff --check
```

Build the ARMv6 adapter when Go code changes.

## Installation and release UX

User entrypoint:

```text
install.sh
```

Maintainer exact-commit deployment:

```bash
scripts/deploy-pi.sh "$(git rev-parse HEAD)"
```

Beginner-facing release bundle:

```bash
scripts/build-release-package.sh "$(git rev-parse HEAD)"
```

Do not add another active deploy script. Historical deployment helpers are retained under `scripts/archive/` only as evidence.

## Documentation

CURRENT docs are listed in `docs/README.md`. Keep that set small and authoritative. Specialized internals belong in `docs/reference/`; completed plans/migrations/old runbooks belong in `docs/archive/`; version history belongs in `docs/releases/`.

Historical content may contain old IPs, versions and procedures. Do not rewrite it to look current.

## Dependencies

Prefer standard library, OS facilities and the official MCP SDK. A new runtime dependency needs a concrete reason plus resource/architecture/rollback analysis.

## Security-sensitive changes

Changes to filesystem mutation, trusted shell, grants, auth, SSH, systemd, audit, update or rollback require negative-path regression coverage where practical. Never commit:

- private keys;
- tokens/passwords/cookies;
- production SQLite databases;
- `.mcp-pi.local.env` or private runtime config.

## Hardware acceptance

Local tests are necessary but not sufficient for a release/deployment change. On the real appliance verify the affected services/endpoints, Doctor and Target path. Keep heavy test/build work off constrained ARMv6 hardware.
