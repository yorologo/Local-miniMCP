# Runbook: Controlled Write Smoke Test

Este runbook describe los pasos para verificar y validar las capacidades de escritura controlada del MCP Gateway en un entorno real.

---

## Prerrequisitos

- Raspberry Pi (`MCP-Pi`, `192.168.68.85`) con servicios `mcp-gateway-admin` y `mcp-gateway-mcp` activos.
- Target Worker (`termux-main`, `192.168.68.84:8022`) alcanzable sin contraseña vía SSH desde la Pi (`mcp-gateway`).
- Directorio de prueba en el Target Worker: `mcp-write-smoke/`.

---

## 1. Verificación Automática Completa (19 Pruebas E2E)

Conectarse a la Raspberry Pi y ejecutar la suite E2E completa:

```bash
ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 /home/mcp-gateway/mcp-gateway/scripts/verify-phase-5.py"
```

Resultado esperado:
```text
=== ALL 19/19 VERIFICATION TESTS PASSED SUCCESSFULLY! ===
```

---

## 2. Verificación Manual Paso a Paso

### 2.1 Inspección de Health y Estado de Escritura

```bash
curl -s http://127.0.0.1:8090/mcp -d '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {"name": "health", "arguments": {}}
}' | jq .
```
Comprobar `"writes_enabled"` en el resultado.

### 2.2 Prueba Negativa: Escrituras Deshabilitadas (Por Defecto)

Intentar sobreescribir un archivo cuando `writes_enabled=false`:
```bash
curl -s http://127.0.0.1:8090/mcp -d '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "write_file",
    "arguments": {
      "target": "termux-main",
      "project": "write_smoke",
      "relative_path": "existing.txt",
      "content": "test\n"
    }
  }
}' | jq .
```
Respuesta esperada:
```json
{
  "ok": false,
  "error": {
    "code": "WRITES_DISABLED",
    "message": "Controlled writes are disabled by administrator setting"
  }
}
```

### 2.3 Simulación Segura (Dry Run)

Habilitar temporalmente las escrituras en `/settings` y probar con `dry_run: true`:
```bash
curl -s http://127.0.0.1:8090/mcp -d '{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "write_file",
    "arguments": {
      "target": "termux-main",
      "project": "write_smoke",
      "relative_path": "existing.txt",
      "content": "new simulated line\n",
      "expected_sha256": "<current-sha>",
      "dry_run": true
    }
  }
}' | jq .
```
Comprobar que se retorna el campo `"diff"` o `"unified_diff"` y que el archivo en el Target Worker permanece intacto.

### 2.4 Control de Pánico: Deshabilitar Escrituras Inmediatamente

Desde la máquina administrativa o por túnel SSH:
```bash
# Vía POST a la consola admin
curl -s -X POST http://127.0.0.1:8080/settings/disable-writes \
  -H "Cookie: session=<admin-cookie>" \
  -d "csrf_token=<token>"
```
Verificar que:
1. `read_file` sigue funcionando al 100%.
2. Cualquier intento de `write_file` es rechazado inmediatamente con `WRITES_DISABLED`.
