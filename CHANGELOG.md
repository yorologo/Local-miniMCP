# Changelog

All notable changes to this project are documented here.

## Unreleased — 1.3.0

### Added
- Trusted Target shell capability (`target_shell`) with independent `shell_enabled` kill switch and readable effective-capability UI.
- Remote Target Environment Facts, deterministic MCP catalog diagnostics, standard Tool Annotations, CI workflow and documentation audit.
- Exact-commit candidate deployment with verified `.deployment.json` provenance and automatic rollback path.
- Optional `age` encryption for private off-device appliance backups; requested encryption fails closed if `age` is unavailable.

### Changed
- Structured filesystem mutations now share remote canonical destination resolution and fail closed on symlink-parent escapes.
- Critical mutations require an available audit sink before execution; `run_task` validates enabled/allowlisted argv/cwd/timeout.
- `run_command` is documented and enforced as a trusted administrative Target shell, not a Project filesystem sandbox.
- systemd hardening was incrementally strengthened without arbitrary memory limits.
- `install.sh` now fails fast on required bootstrap/readiness/Doctor failures.

### Verified
- Full development gate covers Python, Go, ARMv6, JavaScript, Tailwind, documentation and diff hygiene.
- Production acceptance requires exact SHA/provenance, services, endpoints, Doctor, Target, audit and rollback evidence.

### Added
- Full 21-tool MCP catalog including `run_command` and structured filesystem operations.
- GitHub-ready configuration, deployment, troubleshooting, roadmap, contribution, and Mermaid architecture documentation.
- Responsive/accessibility improvements and JavaScript regression coverage for the Admin Console.

### Changed
- Admin Console production access now uses `http://192.168.68.55` on TCP/80, bound to `0.0.0.0` for IPv4 LAN access.
- `mcp-gateway-admin.service` continues to run as `mcp-gateway` and receives only `CAP_NET_BIND_SERVICE` to bind TCP/80.
- Admin security keeps authentication, CSRF, strict CSP/security headers, SameSite cookies, and explicit Host allowlisting.
- Deployment now builds and validates the ARMv6 MCP adapter from current source instead of trusting a stale prebuilt artifact, and avoids unnecessary MCP/tunnel restarts.
- Operational documentation uses the current reserved LAN IP `192.168.68.55` and canonical administrative account `yorologo`.

### Fixed
- Removed stale operational references to Admin port 8080, old LAN addresses, outdated tool counts, and localhost-only Admin assumptions.
- Restored and validated the SSH forced-command wrapper used by Doctor.
- Hardened Admin CSP by removing inline event handlers.

### Verified
- Full local Python suite passes.
- Tailwind and Admin JavaScript checks pass.
- Gateway Doctor reports 19/19 HEALTHY after a full appliance reboot.
- Admin Console survives reboot and is reachable from localhost and trusted LAN on TCP/80.
