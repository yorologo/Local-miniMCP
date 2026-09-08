# Runbook: Respaldo, Restauración y Migración del Registro SQLite

Este runbook detalla los procedimientos de respaldo, restauración, exportación saneada y rollback del Registro Persistente de MCP Gateway en la Raspberry Pi.

---

## 1. Copias de Seguridad del Registro (Backup Online)

El comando `mcp_gateway.admin_cli backup` utiliza la API nativa de respaldo en línea de SQLite (`sqlite3.Connection.backup()`), lo que garantiza copias consistentes y atómicas sin necesidad de detener el servicio ni riesgo de corrupción por escrituras concurrentes.

### 1.1 Ejecución Manual de Respaldo
En la Raspberry Pi (`MCP-Pi`):

```bash
ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.admin_cli backup"
```

**Salida típica:**
```text
Backup created successfully: /home/mcp-gateway/.local/share/mcp-gateway/gateway.db.backup-20260908-154000
```

### 1.2 Especificar Ruta de Destino Personalizada
```bash
sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.admin_cli backup --dest /tmp/backup_gateway.db
```

---

## 2. Exportación Saneada en Formato JSON

Para compartir configuraciones, crear plantillas o respaldar la topología sin exponer secretos:

```bash
ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.admin_cli export-json --output /home/mcp-gateway/targets-export.json"
```

### Propiedades de la Exportación Saneada:
- **Cero Secretos**: No incluye contraseñas ni hashes PBKDF2 de usuarios administradores.
- **Cero Claves de Sesión**: No incluye tokens CSRF ni llaves de cifrado de cookies.
- **Formato Estándar**: Estructura compatible con `config/targets.local.json` y el comando `import-json`.

---

## 3. Restauración de Base de Datos SQLite

Si la base de datos se corrompe o requiere regresar a un estado previo:

### Paso 1: Detener el Servicio Web
```bash
sudo systemctl stop mcp-gateway-admin
```

### Paso 2: Reemplazar el Archivo de Base de Datos
```bash
sudo -u mcp-gateway cp /home/mcp-gateway/.local/share/mcp-gateway/gateway.db.backup-20260908-154000 /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
```

### Paso 3: Verificar Permisos
Asegurar que el archivo mantenga la propiedad `mcp-gateway:mcp-gateway`:
```bash
sudo chown mcp-gateway:mcp-gateway /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
sudo chmod 644 /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
```

### Paso 4: Iniciar el Servicio
```bash
sudo systemctl start mcp-gateway-admin
sudo systemctl status mcp-gateway-admin
```

---

## 4. Importar Configuración desde un Archivo JSON

Para poblar o sincronizar el registro SQLite a partir de un archivo JSON estructurado:

```bash
sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.admin_cli import-json /ruta/al/targets.json
```

El proceso es idempotente: actualiza targets y proyectos existentes y crea los que falten.

---

## 5. Procedimiento de Rollback a Backend JSON

Si por cualquier contingencia o degradación se requiere prescindir de SQLite y retornar al funcionamiento exclusivo basado en archivos JSON de la Fase 4A:

1. **Configurar Variable de Entorno**:
   El Gateway y la CLI soportan la variable `MCP_GATEWAY_REGISTRY=json`.

   Para la CLI:
   ```bash
   export MCP_GATEWAY_REGISTRY=json
   python3 -m mcp_gateway.cli --config config/targets.local.json health
   ```

2. **Rollback en el Servicio systemd (Opcional)**:
   Si se requiere configurar el servicio con fallback JSON, añadir al archivo `/etc/systemd/system/mcp-gateway-admin.service`:
   ```ini
   Environment="MCP_GATEWAY_REGISTRY=json"
   Environment="MCP_GATEWAY_CONFIG=/home/mcp-gateway/mcp-gateway/config/targets.local.json"
   ```
   seguido de `sudo systemctl daemon-reload && sudo systemctl restart mcp-gateway-admin`.

---

## 6. Control de Versiones del Esquema (Schema Migration)

La base de datos utiliza `PRAGMA user_version` de SQLite para llevar el control estricto de versión de esquema:
- Versión actual: `PRAGMA user_version = 1`.
- Al inicializarse la base de datos (`init_db()`), se valida que la versión coincida con `SCHEMA_VERSION = 1`.
- Las migraciones futuras se ejecutan de manera incremental y controlada mediante la función `migrate_db(conn)`.
