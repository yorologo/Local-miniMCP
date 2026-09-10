# Runbook: MCP Gateway Doctor & Diagnostics

Este runbook detalla los procedimientos para diagnosticar el estado del Gateway, verificar la salud del runtime y ejecutar reparaciones no destructivas.

---

## Prerrequisitos

- Acceso SSH administrativo a `MCP-Pi` (`192.168.68.85`) con usuario `yorologo`.
- Servicios del Gateway instalados en `/home/mcp-gateway/mcp-gateway`.

---

## 1. Diagnóstico Mediante CLI Unificado

Conectarse a la Raspberry Pi y ejecutar `doctor`:

```bash
ssh yorologo@192.168.68.85 "sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway doctor"
```

### Salida Esperada

```text
==================================================
=== MCP GATEWAY DOCTOR: SYSTEM HEALTH CHECK    ===
==================================================
[PASS] Python Runtime               : Python 3.13.5 (Trixie) / 3.9.2 (Bullseye)
[PASS] Architecture                 : System architecture: armv6l
[PASS] Compatibility Contract       : Loaded from /home/mcp-gateway/mcp-gateway/compatibility.json (Gateway v1.0.1)
[PASS] SQLite Integrity             : Database integrity ok (/home/mcp-gateway/.local/share/mcp-gateway/gateway.db)
[PASS] Schema Version               : Schema user_version=1 (expected >=1)
[PASS] Data Directory Permissions   : /home/mcp-gateway/.local/share/mcp-gateway mode is 0o700
[PASS] SSH Key Permissions          : /home/mcp-gateway/.ssh/mcp_gateway_ed25519 mode is 0o600
[PASS] Gateway Core Health          : Core status ok (writes_enabled=False)
[PASS] Tool Catalog                 : Catalog contains 9 tools in deterministic order
[PASS] MCP HTTP /live               : Liveness probe returned 200 OK
[PASS] MCP HTTP /ready              : Readiness probe returned 200 OK
[PASS] MCP Host Protection          : Malicious Host header rejected with HTTP 403
[PASS] MCP Origin Protection        : Malicious Origin rejected with HTTP 403
==================================================
OVERALL STATUS: HEALTHY
==================================================
```

---

## 2. Auto-Reparación Segura (`repair`)

Si se reportan advertencias o fallos menores de permisos:

```bash
ssh yorologo@192.168.68.85 "sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway repair"
```

Acciones que ejecuta automáticamente:
- Restablece permisos `0700` en directorios de datos y configuración.
- Restablece permisos `0600` en claves privadas SSH.
- Recarga configuración de servicios en background.

---

## 3. Diagnóstico Vía Interfaz Web

1. Abrir un túnel SSH a la consola administrativa:
   ```bash
   ssh -N -L 8080:127.0.0.1:8080 yorologo@192.168.68.85
   ```
2. Navegar en el navegador a: `http://127.0.0.1:8080/maintenance`
3. Revisar el widget de **Doctor Health Check** y hacer clic en **Re-run Diagnostics** o **Execute Safe Repair** según corresponda.
