# Runbook: Recuperación ante Desastres (Disaster Recovery) — MCP-Pi v1.2.1

> Procedimiento canónico de respaldo y reconstrucción limpia del appliance **MCP-Pi Gateway (v1.2.1)** ante pérdida catastrófica de medio de arranque (microSD), daño de hardware o contingencia mayor.

---

## 1. Escenario de Desastre

- Fallo catastrófico, corrupción de almacenamiento físico (microSD) o reemplazo de la placa Raspberry Pi Model A+ Rev 1.1.
- Reconstrucción limpia requerida sobre **Raspberry Pi OS Lite 32-bit (Debian 13 Trixie armv6l)**.
- Retención determinista de identidades criptográficas, pinning de targets, credenciales de túnel seguro y base de datos SQLite.

---

## 2. Inventario de Componentes para la Recuperación

La recuperación se basa en la separación estricta entre **artefactos reproducibles desde Git** y **estado persistente / identidades privadas**:

| Componente | Clasificación | Fuente de Verdad / Mecanismo |
|---|---|---|
| Código fuente y compatibilidad | Reproducible | Repositorio Git (`tag v1.2.1` en GitHub) |
| Binario MCP Adapter (`armv6`) | Reproducible | Release artifact / build Go ARMv6 (`mcp-gateway-adapter`) |
| Binario OpenAI Tunnel Client | Reproducible | Binario oficial `openai-tunnel-client` (Linux ARMv6) |
| Systemd unit definitions | Reproducible | Repositorio Git (`config/systemd/`) |
| Script `mcp-gateway-tunnel-check` | Reproducible | Repositorio Git (`config/systemd/mcp-gateway-tunnel-check`) |
| Base de datos `gateway.db` | Stateful | Respaldo privado (`data/gateway.db`, SQLite snapshot online) |
| Host Keys SSH (`/etc/ssh/ssh_host_*`) | Secreto / Identidad | Respaldo privado (`host-ssh/`, ED25519 `SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E`) |
| Client Key SSH (`mcp_gateway_ed25519`) | Secreto / Identidad | Respaldo privado (`gateway-ssh/`, ED25519 `SHA256:Vd61kRdCrV+JbNYnPyKPLVEQBi7xsQ24Dbug+epdMEY`) |
| Target Pinned Keys (`known_hosts`, `config`) | Stateful | Respaldo privado (`gateway-ssh/known_hosts`, `config`) |
| Credenciales de Túnel (`tunnel.env`) | Secreto | Respaldo privado (`config/tunnel.env`, mode `0600`) |
| Token interno de autenticación MCP | Secreto | Respaldo privado (`config/tunnel-mcp.token`, mode `0600`) |
| Secreto de Consola Admin (`admin-secret`) | Secreto | Respaldo privado (`config/admin-secret`, mode `0600`) |
| Claves de acceso admin (`authorized_keys`) | Stateful | Respaldo privado (`admin-ssh/authorized_keys`, mode `0600`) |

---

## 3. Generación del Respaldo (Backup KISS)

El script canónico `scripts/backup-appliance.sh` genera un snapshot seguro y atómico en caliente sin requerir detención del servicio:

```bash
# En MCP-Pi (ejecutado por root o via sudo)
sudo /home/mcp-gateway/mcp-gateway/scripts/backup-appliance.sh /home/yorologo/backups
```

El script ejecuta automáticamente:
1. Verificación de privilegios de ejecución y espacio disponible en disco (mínimo 50 MB requeridos).
2. Creación de snapshot online atómico de `gateway.db` mediante la API nativa de SQLite en Python (`sqlite3.Connection.backup()`).
3. Validación inmediata de la integridad del snapshot (`PRAGMA integrity_check == 'ok'`).
4. Recolección de archivos de configuración, secretos e identidades preservando permisos exactos.
5. Generación de manifiesto no secreto `manifest.json` con metadatos, fingerprints y sumas SHA256 de cada archivo.
6. Empaquetado en archivo tarball comprimido con permisos restringidos `0600` (`mcp-pi-v1.2.1-<TIMESTAMP>.tar.gz`).
7. Generación de suma criptográfica SHA256 (`.tar.gz.sha256`).
8. Limpieza garantizada del directorio temporal de staging.

---

## 4. Procedimiento de Restauración Paso a Paso (Fresh Install)

Escenario base: **Fresh Debian 13 Trixie ARMv6 + Git tag v1.2.1 + Respaldo privado de estado**.

### Paso 1: Preparar OS y Usuarios
1. Grabar microSD limpia con Raspberry Pi OS Lite 32-bit (Debian 13 Trixie).
2. Configurar usuario administrativo inicial `yorologo` (UID 1000, sudoer) y red Wi-Fi.
3. Crear cuenta de servicio del Gateway con permisos mínimos (sin sudo):
   ```bash
   sudo groupadd -g 105 mcp-gateway || true
   sudo useradd -u 102 -g 105 -d /home/mcp-gateway -m -s /bin/bash mcp-gateway || true
   ```

### Paso 2: Instalar Release de Software
1. Clonar el repositorio oficial e inicializarlo en el tag congelado `v1.2.1`:
   ```bash
   sudo -u mcp-gateway git clone https://github.com/yorologo/Local-miniMCP.git /home/mcp-gateway/mcp-gateway
   cd /home/mcp-gateway/mcp-gateway
   sudo -u mcp-gateway git checkout v1.2.1
   ```
2. Instalar o compilar el binario ARMv6 `bin/mcp-gateway-adapter`:
   ```bash
   sudo chmod +x /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter
   ```
3. Instalar el binario `openai-tunnel-client` en `/usr/local/bin/openai-tunnel-client` (modo 0755, root:root).
4. Copiar el helper de verificación de túnel:
   ```bash
   sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-tunnel-check /usr/local/bin/
   sudo chmod 755 /usr/local/bin/mcp-gateway-tunnel-check
   sudo chown root:root /usr/local/bin/mcp-gateway-tunnel-check
   ```

### Paso 3: Detener Servicios (si estuvieran activos)
```bash
sudo systemctl stop mcp-gateway-tunnel.service mcp-gateway-mcp.service mcp-gateway-admin.service || true
```

### Paso 4: Restaurar Base de Datos y Estado Persistente
Desde el archivo de respaldo `mcp-pi-v1.2.1-<TIMESTAMP>.tar.gz` extraído en un directorio temporal aislado `/tmp/restore`:
```bash
sudo mkdir -p /home/mcp-gateway/.local/share/mcp-gateway
sudo cp /tmp/restore/data/gateway.db /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/.local/share/mcp-gateway
sudo chmod 700 /home/mcp-gateway/.local/share/mcp-gateway
sudo chmod 600 /home/mcp-gateway/.local/share/mcp-gateway/gateway.db

# Verificar integridad de la base restaurada
sudo -u mcp-gateway python3 -c "import sqlite3; c=sqlite3.connect('/home/mcp-gateway/.local/share/mcp-gateway/gateway.db'); assert c.cursor().execute('PRAGMA integrity_check;').fetchone()[0]=='ok'; print('DB Restore OK')"
```

### Paso 5: Restaurar Identidades y Secretos con Permisos Estrictos
1. **Host Keys SSH de MCP-Pi**:
   ```bash
   sudo cp /tmp/restore/host-ssh/ssh_host_* /etc/ssh/
   sudo chown root:root /etc/ssh/ssh_host_*
   sudo chmod 600 /etc/ssh/ssh_host_*_key
   sudo chmod 644 /etc/ssh/ssh_host_*_key.pub
   sudo systemctl restart ssh
   ```
2. **Identidad SSH del Gateway y Pinned Keys**:
   ```bash
   sudo mkdir -p /home/mcp-gateway/.ssh
   sudo cp /tmp/restore/gateway-ssh/* /home/mcp-gateway/.ssh/
   sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/.ssh
   sudo chmod 700 /home/mcp-gateway/.ssh
   sudo chmod 600 /home/mcp-gateway/.ssh/mcp_gateway_ed25519
   sudo chmod 644 /home/mcp-gateway/.ssh/mcp_gateway_ed25519.pub
   sudo chmod 644 /home/mcp-gateway/.ssh/known_hosts
   sudo chmod 600 /home/mcp-gateway/.ssh/config
   ```
3. **Credenciales y Tokens**:
   ```bash
   sudo mkdir -p /home/mcp-gateway/.config/mcp-gateway
   sudo cp /tmp/restore/config/* /home/mcp-gateway/.config/mcp-gateway/
   sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/.config/mcp-gateway
   sudo chmod 700 /home/mcp-gateway/.config/mcp-gateway
   sudo chmod 600 /home/mcp-gateway/.config/mcp-gateway/*
   ```
4. **Claves de Acceso de Administrador**:
   ```bash
   mkdir -p /home/yorologo/.ssh
   cp /tmp/restore/admin-ssh/authorized_keys /home/yorologo/.ssh/
   chmod 700 /home/yorologo/.ssh
   chmod 600 /home/yorologo/.ssh/authorized_keys
   ```

### Paso 6: Instalar Configuración de Systemd
```bash
sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-admin.service /etc/systemd/system/
sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-mcp.service /etc/systemd/system/
sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-tunnel.service /etc/systemd/system/
sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-postboot.service /etc/systemd/system/
sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-maintenance.service /etc/systemd/system/
sudo cp /home/mcp-gateway/mcp-gateway/config/systemd/mcp-gateway-maintenance.timer /etc/systemd/system/
```

### Paso 7: Systemd Daemon Reload
```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-gateway-admin.service mcp-gateway-mcp.service mcp-gateway-tunnel.service mcp-gateway-postboot.service mcp-gateway-maintenance.timer
```

### Paso 8: Arrancar Servicios del Gateway
```bash
sudo systemctl start mcp-gateway-admin.service
sudo systemctl start mcp-gateway-mcp.service
```

### Paso 9: Validar Gateway Doctor
```bash
sudo -u mcp-gateway python3 -c '
import sys
sys.path.insert(0, "/home/mcp-gateway/mcp-gateway/src")
from mcp_gateway.doctor import run_doctor
overall, checks = run_doctor()
print("DOCTOR OVERALL:", overall)
assert overall == "HEALTHY", "Doctor verification failed!"
'
```
Resultado requerido: `HEALTHY` (19/19 checks passed).

### Paso 10: Arrancar y Validar Secure MCP Tunnel
```bash
sudo systemctl start mcp-gateway-tunnel.service
sudo systemctl status mcp-gateway-tunnel.service --no-pager
```
Verificar que `mcp-gateway-tunnel-check` complete exitosamente y el servicio reporte estado `active (running)`.

### Paso 11: Validar Target Remoto
Verificar la conectividad hacia el target autorizado (`termux-main`):
```bash
sudo -u mcp-gateway ssh -F /home/mcp-gateway/.ssh/config termux-local "echo TARGET_HEALTHY"
```
Resultado requerido: `TARGET_HEALTHY` sin advertencias de host key.

---

## 5. Diseño de Aceptación Futura (Future Non-Destructive Acceptance Test)

Para certificar la reproducibilidad completa del Disaster Recovery sin destruir ni interrumpir la producción actual:

1. **Entorno**: Ejecución sobre medio de almacenamiento secundario (spare microSD) o en contenedor/chroot aislado en el propio hardware ARMv6 (sin relajar políticas de seguridad ni usar PRoot).
2. **Secuencia de Verificación**:
   ```text
   BACKUP_CREATED (scripts/backup-appliance.sh)
   → RESTORE_FROM_CLEAN_BASE (aplicación del runbook en entorno limpio)
   → IDENTITIES_PRESERVED (host fingerprint, client key, target pin intactos)
   → DB_OK (integridad SQLite ok, row counts idénticos)
   → DOCTOR_PASS (19/19 checks HEALTHY)
   → TARGET_PASS (conexión al target y tools operacionales)
   ```
3. **Criterio de Aprobación**: El entorno restaurado debe alcanzar funcionalidad idéntica a la línea base de producción actual v1.2.1 sin intervención manual correctiva.
