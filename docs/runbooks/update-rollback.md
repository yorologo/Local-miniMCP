# Runbook: MCP Gateway Safe Updates & Rollback

Este runbook detalla los procedimientos para respaldar, actualizar de forma segura y revertir versiones del Gateway ante anomalías.

---

## 1. Respaldo Online de Base de Datos

Antes de cualquier actualización o cambio de esquema:

```bash
# Vía CLI como mcp-gateway:
sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway backup
```

Salida esperada:
```text
Online database backup created successfully: /home/mcp-gateway/.local/share/mcp-gateway/backups/gateway_backup_YYYYMMDD_HHMMSS.db
```

También puede generarse desde la consola web en `/maintenance` pulsando **Create Backup**.

---

## 2. Restauración de Base de Datos

En caso de corrupción o necesidad de regresar a un estado previo:

```bash
sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway restore /home/mcp-gateway/.local/share/mcp-gateway/backups/<backup_name>.db
```

El comando valida automáticamente:
1. Existencia del archivo de respaldo.
2. Integridad de la base de datos (`PRAGMA integrity_check`).
3. Compatibilidad de versión de esquema (`user_version >= 1`).
4. Reemplazo online no destructivo mediante la API SQLite `backup()`.

---

## 3. Reversión de Release (*Rollback*)

Si se utilizan symlinks de release (`current` y `previous`):

```bash
# Vía CLI:
sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway rollback
```

O desde la interfaz web `/maintenance` mediante el botón **Execute Rollback**.

El sistema:
1. Comprueba la existencia de la versión anterior en `releases/`.
2. Verifica la compatibilidad de `manifest.json` de la versión anterior.
3. Realiza un swap atómico del symlink `current`.
4. Reinicia ordenadamente los servicios `mcp-gateway-admin` y `mcp-gateway-mcp`.
