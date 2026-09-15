# Update and rollback

MCP-Pi deliberately separates **user release updates** from **maintainer exact-commit deployments**.

## User update

Obtain and extract the new official release bundle on the appliance, then:

```bash
./install.sh --check
sudo ./install.sh
```

The installer preserves persistent Registry/config/secrets, stages the application, retains the previous installer-managed runtime and verifies services/Doctor before declaring success.

If the source is only being inspected, `--check` makes no system changes.

## User rollback

When an installer-managed previous runtime exists:

```bash
sudo /home/mcp-gateway/mcp-gateway/install.sh --rollback
```

A successful rollback prints:

```text
ROLLBACK_VERIFIED
```

only after previous runtime/units are restored and health checks recover.

## Candidate validation from CLI

`mcp-gateway update` no longer silently uses the old symlink lifecycle as production update logic. It can validate a candidate package/directory:

```bash
sudo -u mcp-gateway mcp-gateway update /path/to/candidate --check
```

Actual application replacement is a root-level operation handled by `install.sh`.

## Maintainer exact-commit deployment

Maintainers promoting a tested Git commit to a known appliance should launch the long operation through the resumable runner:

```bash
SHA="$(git rev-parse HEAD)"
JOB="deploy-${SHA:0:12}"
scripts/run-resumable.sh start \
  --expect-marker DEPLOYMENT_VERIFIED \
  "$JOB" -- scripts/deploy-pi.sh "$SHA"
```

If the tool window disconnects, do not rerun the deploy. A normal self-restarting deployment logs `CONTROL_PLANE_RESTART=EXPECTED` before the outage and `CONTROL_PLANE_RESTORED` after MCP readiness and Tunnel recovery. Reconstruct state first:

```bash
scripts/run-resumable.sh status "$JOB"
scripts/run-resumable.sh log "$JOB" 120
```

Direct execution is intentionally rejected because this deploy restarts the same MCP/Tunnel control plane used by automation. Use the resumable runner even from an attached maintainer shell. `MCP_DEPLOY_ALLOW_DIRECT=1` is break-glass recovery only and must never be the normal release path.

This path requires:

- clean worktree;
- requested SHA == local HEAD == `origin/<branch>`;
- deterministic `git archive` package;
- ARMv6 adapter built from that archive;
- candidate validation on the real appliance;
- runtime + unit rollback set;
- control-plane-safe restart order;
- lightweight production acceptance;
- `.deployment.json` provenance with `verified=true` only after acceptance.

This is a development/release engineering mechanism, **not** the first-install guide.

If the same SHA is already recorded as verified and Admin/MCP/Tunnel are healthy, `deploy-pi.sh` returns `ALREADY_DEPLOYED` plus `DEPLOYMENT_VERIFIED` without mutating production. `MCP_DEPLOY_FORCE=1` bypasses that protection only for an intentional repair/redeployment; controlled failure injection also bypasses it so rollback tests remain meaningful.

## Maintainer release bundle

After a release candidate is committed and the worktree is clean:

```bash
scripts/build-release-package.sh "$(git rev-parse HEAD)"
```

The produced ARMv6 release bundle includes a prebuilt adapter plus `SHA256SUMS`, allowing a constrained appliance to install without Go.

## Controlled deploy rollback test

For maintainers only, `deploy-pi.sh` supports a deliberate failure injection to prove rollback. Do not use it as routine user rollback.

```bash
JOB="rollback-test-${SHA:0:12}"
scripts/run-resumable.sh start "$JOB" -- \
  env MCP_DEPLOY_INJECT_FAILURE=after-activation scripts/deploy-pi.sh "$SHA"
```

The test is successful only when the command fails by design **and** the previous runtime is independently verified healthy afterward.

## Database backup versus application rollback

These are separate concerns:

```text
Application rollback -> previous runtime + units
Registry restore      -> SQLite backup
```

An application rollback must not silently replace or destroy persistent user data. See [recovery.md](recovery.md).
