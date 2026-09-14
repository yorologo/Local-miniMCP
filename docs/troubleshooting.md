# Troubleshooting

## MCP-Pi cannot reach `termux-main`

Symptoms include `No route to host`, `Connection refused`, or `SSH_TIMEOUT` on port `8022`.

1. Confirm the Android device is actually connected to the same Wi-Fi/LAN.
2. Restart Termux SSH:
   ```bash
   pkill sshd 2>/dev/null
   sshd
   ```
3. On non-root Android, `ip`/`ss` may fail because netlink access is restricted. If Shizuku/rish is available, inspect networking through the shell UID instead.
4. Retry `target_status` or a harmless `run_command` through MCP-Pi. Dynamic endpoint discovery can update a stale target IP only when the device is reachable on the LAN.

## ChatGPT sees fewer than 21 tools

The Gateway Core catalog contains 21 tools. If ChatGPT receives fewer:

- verify `gateway_doctor` reports `Catalog contains 21 tools`;
- verify the Go adapter advertises `capabilities.tools.listChanged=true`;
- confirm the OpenAI tunnel is connected;
- inspect real `tools/list` traffic through the tunnel;
- distinguish server-side catalog count from the catalog actually projected into the ChatGPT plugin session.

Do not change grants or delete the registry until you know at which hop the count changes.

## Admin Console returns 403 on LAN

The Admin Console validates the HTTP `Host` header. Production allows `192.168.68.55`, `mcp-pi`, `localhost`, and `127.0.0.1`. If the address changes, update both `MCP_ADMIN_HOST` and `MCP_ADMIN_ALLOWED_HOSTS` in the systemd unit/environment, reload systemd, and restart `mcp-gateway-admin`.

## Admin Console does not load styles or scripts

Rebuild static CSS and rerun the JS test:

```bash
cd tailwind && npm run build
cd ..
node tests/test_app_js.mjs
```

The production Pi does not need Node.js; compiled assets are deployed from the development machine.

## `WRITES_DISABLED`

The structured filesystem tools (`write_file`, `append_file`, `delete_file`, `copy_file`, `move_file`, `mkdir`) require the global write switch plus project write permission. `run_command` is a separate execute capability and is controlled by its grant/project scope rather than the structured-write switch.

## Deployment fails before tests

Check `.mcp-pi.local.env`, SSH reachability to `192.168.68.55`, and host-key state. Do not disable strict host-key checking as a shortcut on production paths.
