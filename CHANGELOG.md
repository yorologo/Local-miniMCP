# Changelog

All notable user-visible changes are documented here. Historical release details remain under `docs/releases/`.

## 1.3.0 — 2026-09-15

### Added
- Resumable long-job runner using `nohup` + `setsid` + `flock`, durable non-secret state, explicit status/log/cleanup, optional short-lived Termux wake lock, and no automatic retries after interrupted control sessions.

- trusted Target-shell capability with independent `shell_enabled` kill switch and readable effective-capability UI;
- Target Environment Facts, deterministic MCP catalog diagnostics and standard Tool Annotations;
- CI and semantic documentation audit;
- exact-commit maintainer deployment with verified `.deployment.json` provenance and transactional rollback;
- optional fail-closed `age` encryption for private off-device backups;
- beginner-facing release-package builder with prebuilt ARMv6 adapter;
- source/release-tree installer preflight (`install.sh --check`) and installer-managed rollback;
- minimal real Admin bootstrap through `mcp-gateway setup`.

### Changed
- Exact-commit deployment now exits safely as `ALREADY_DEPLOYED` when the same verified SHA is already healthy; `MCP_DEPLOY_FORCE=1` is the explicit repair override.

- structured filesystem mutations share remote canonical destination resolution and reject symlink-parent escapes;
- critical mutations require audit availability before execution;
- `run_task` validates enabled/allowlisted argv/cwd/timeout;
- `run_command` is explicitly a trusted Target shell, not a Project filesystem sandbox;
- systemd hardening was strengthened without arbitrary memory limits;
- Admin systemd defaults are generic/loopback-safe; machine-specific trusted-LAN binding lives in private `admin.env`;
- fresh Registry defaults keep both structured writes and trusted Target shell disabled;
- `install.sh` now installs from the directory containing the release/source, preserves persistent state, stages application updates, verifies readiness/Doctor and provides rollback;
- `mcp-gateway update/rollback` no longer present the historical symlink lifecycle as the production update path;
- active documentation is consolidated into a small CURRENT set; technical detail and historical evidence are separated into `reference/` and `archive/`;
- only `scripts/deploy-pi.sh` remains an active production deploy entrypoint.

### Fixed

- transactional maintainer rollback reads protected systemd unit backups with required privilege and propagates remote rollback failures instead of emitting false success;
- stale documentation assumptions about old IPs, tool counts, release baselines and setup behavior are removed from CURRENT guidance;
- installer no longer assumes application files are already copied into `/home/mcp-gateway/mcp-gateway`.

### Verification

1.3.0 promotion requires Python, Go, ARMv6 build, JavaScript, Tailwind, documentation, release-package, installer preflight, CI, exact-commit production deployment and live acceptance gates to pass on the same final commit.
