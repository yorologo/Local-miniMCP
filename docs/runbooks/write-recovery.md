# Runbook: Write Recovery & Backup Restoration

Este runbook describe el procedimiento para restaurar un archivo a una versión previa utilizando los respaldos automáticos generados por el MCP Gateway en la Raspberry Pi.

---

## 1. Almacenamiento de Respaldos

Antes de cualquier operación destructiva o de sobreescritura exitosa, el MCP Gateway almacena automáticamente una copia exacta del archivo existente en la Raspberry Pi bajo la cuenta de servicio `mcp-gateway`:

```text
/home/mcp-gateway/.local/share/mcp-gateway/backups/<TARGET>/<PROJECT>/<RELATIVE_PATH>/
```

### Estructura de Nombres de Archivo
Cada archivo de respaldo sigue el formato:
```text
YYYYMMDD_HHMMSS_<SHA256_PREFIX>.bak
```
Ejemplo: `20260908_170706_a948904f2f0f.bak`.

### Política de Retención
El gateway mantiene un máximo de **5 respaldos rodantes** por archivo. Al crearse el sexto respaldo, la versión más antigua es eliminada automáticamente.

---

## 2. Procedimiento de Restauración

### Paso 1: Listar Respaldos Disponibles

En la Raspberry Pi:
```bash
sudo -u mcp-gateway ls -la "/home/mcp-gateway/.local/share/mcp-gateway/backups/<TARGET>/<PROJECT>/<PATH>/"
```

### Paso 2: Comparar Contenido o Verificar Hash

Inspeccionar el contenido del respaldo deseado:
```bash
sudo -u mcp-gateway sha256sum "/home/mcp-gateway/.local/share/mcp-gateway/backups/<TARGET>/<PROJECT>/<PATH>/<BACKUP_FILE>.bak"
```

### Paso 3: Restaurar en el Target Worker

#### Opción A: Restauración Vía Gateway MCP (Recomendada)
Si las escrituras están habilitadas y se cuenta con el cliente MCP, invocar `write_file` pasando el contenido del respaldo y el `expected_sha256` actual del archivo.

#### Opción B: Restauración Manual Vía SSH Directo desde la Pi
Si el Gateway tiene las escrituras deshabilitadas o se requiere intervención administrativa directa:

```bash
# Como usuario mcp-gateway en MCP-Pi:
cat "/home/mcp-gateway/.local/share/mcp-gateway/backups/<TARGET>/<PROJECT>/<PATH>/<BACKUP_FILE>.bak" | \
  ssh <TARGET_ALIAS> "cat > '<PROJECT_ROOT>/<PATH>'"
```

Ejemplo real para `termux-main` / `write_smoke`:
```bash
sudo -u mcp-gateway bash -c '
BACKUP=$(ls -t /home/mcp-gateway/.local/share/mcp-gateway/backups/termux-main/write_smoke/existing.txt/*.bak | head -1)
cat "$BACKUP" | ssh termux-local "cat > /data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-write-smoke/existing.txt"
'
```

### Paso 4: Validar Restauración

Verificar el hash resultante en el Target Worker:
```bash
sudo -u mcp-gateway ssh termux-local "sha256sum /data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-write-smoke/existing.txt"
```
Comprobar que coincide exactamente con el SHA256 esperado.
