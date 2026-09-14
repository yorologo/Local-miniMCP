# Changelog

All notable changes to this project are documented here.

## Unreleased

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
