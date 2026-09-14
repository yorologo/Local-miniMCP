# Contributing to Local-miniMCP / MCP-Pi

Local-miniMCP is intentionally small, security-sensitive, and optimized for low-resource ARMv6 hardware. Contributions should preserve that character.

## Principles

- Prefer KISS over abstraction for its own sake.
- Reuse the Python standard library, system tools, and the official MCP SDK before adding dependencies.
- Keep the Gateway Core as the single policy authority.
- Preserve deny-by-default behavior and explicit client grants.
- Do not weaken path confinement, SSH host-key pinning, CSRF, Host/Origin checks, or kill switches.
- Do not mix MCP-Pi with the separate Pi-hole appliance.

## Development flow

1. Work from a feature branch based on `develop`.
2. Make the smallest coherent change.
3. Run the full Python suite:
   ```bash
   python -m unittest discover -s tests -p 'test_*.py' -v
   ```
4. If frontend files changed, also run:
   ```bash
   node tests/test_app_js.mjs
   cd tailwind && npm run build
   ```
5. Run `git diff --check` and review the complete diff.
6. Update documentation in the same change whenever behavior, commands, ports, schemas, tools, or deployment change.

## Documentation requirements

Keep `README.md`, `AGENTS.md`, `docs/`, examples, troubleshooting, Mermaid diagrams, and deployment instructions aligned with the implementation. Historical evidence under `docs/releases/`, `docs/inventory/`, `docs/migration/`, and `docs/superpowers/` should remain historically accurate rather than being rewritten as current state.

## Dependencies

New runtime dependencies require a concrete reason. On Raspberry Pi Model A+, memory, startup cost, architecture availability, maintenance burden, and rollback impact all matter.

## Security-sensitive changes

Changes involving `run_command`, filesystem mutation tools, grants, authentication, tunnel configuration, SSH, or systemd must include negative-path tests where practical. Never commit credentials, private keys, tokens, cookies, production databases, or `.mcp-pi.local.env`.

## Deployment acceptance

A change is not complete just because tests pass locally. For release/deployment work, validate the live services on MCP-Pi, confirm the Admin Console responds, and run `mcp-gateway doctor` or the equivalent gateway health check.
