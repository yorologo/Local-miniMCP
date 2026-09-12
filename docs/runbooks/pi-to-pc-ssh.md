# Runbook: Canal SSH Seguro Raspberry Pi (MCP-Pi) → Target Worker (termux-main)

Este documento detalla la arquitectura técnica, configuración, invariantes de seguridad y procedimientos de resiliencia del canal SSH unidireccional establecido entre el Gateway MCP en la Raspberry Pi y el Target Worker Android (`termux-main`).

---

## 1. Identidades de los Nodos

### Raspberry Pi (Gateway)
- **Hostname**: `MCP-Pi`
- **Dirección IPv4 LAN**: `192.168.68.85`
- **Dirección MAC LAN**: `8c:90:2d:ac:e5:c0`
- **Usuario de servicio**: `mcp-gateway` (UID 102, GID 105 en producción Debian 13 Trixie; histórico Bullseye: UID 1001, GID 1001; sin sudo, sin login interactivo por contraseña)
- **Ruta de clave privada**: `/home/mcp-gateway/.ssh/mcp_gateway_ed25519` (permisos 600, retenida exclusivamente en MCP-Pi)
- **Huella de clave pública Gateway (Ed25519)**: `SHA256:Vd61kRdCrV+JbNYnPyKPLVEQBi7xsQ24Dbug+epdMEY mcp-gateway@MCP-Pi`

### Target Worker Android (Worker)
- **Target ID Canónico**: `termux-main`
- **Alias SSH Canónico**: `termux-local` (`pc-local` retenido exclusivamente por compatibilidad hacia atrás)
- **Hostname**: `localhost`
- **Sistema Operativo**: `Linux (Android 16 / Termux aarch64)`
- **Dirección IPv4 LAN**: `192.168.68.84` (endpoint mutable asignado por DHCP; `IP != IDENTITY`)
- **Dirección MAC LAN**: `22:b6:b2:e3:73:65`
- **Interfaz LAN activa**: `wlan0`
- **Servidor SSH**: OpenSSH Server en puerto `8022` (puerto estándar sin privilegios root en sandbox de Termux)
- **Identidad en el servidor**: `u0_a435` (cuenta de app no root, contexto `u:r:untrusted_app_27`, sin sudo, sin su)
- **Huella del Host (Host Fingerprint Inmutable)**: `SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0 (ED25519)`

---

## 2. Configuración SSH y Resolución de Identidad

En `MCP-Pi`, el archivo `/home/mcp-gateway/.ssh/config` (permisos 600) define el host y sus alias:

```sshconfig
Host termux-local pc-local
    HostName 192.168.68.84
    Port 8022
    User u0_a435
    IdentityFile ~/.ssh/mcp_gateway_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking yes
    ConnectTimeout 10
```

El archivo `/home/mcp-gateway/.ssh/known_hosts` (permisos 644) fija criptográficamente la clave pública del host para prevenir ataques de intermediario (MITM) bajo política estricta (`StrictHostKeyChecking yes`):

```text
[192.168.68.84]:8022,[192.168.68.72]:8022,[10.31.245.25]:8022,termux-main,termux-local,pc-local ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIO558VBc3DlRhK/vRg5CPZV4kTD0DaY5GXoEEvjyCLmR
```

> **Regla Operativa (IP != IDENTITY):** Ante un cambio de asignación DHCP de la IP del teléfono, se debe verificar que la huella SSH coincida exactamente con `SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`. Solo tras la validación criptográfica se actualizan `known_hosts`, `config` y `gateway.db`.

---

## 3. Arquitectura de Resiliencia y Auto-Recuperación (Self-Healing)

Para garantizar disponibilidad continua y recuperación automática desatendida ante Doze, recolección de procesos por memoria o fallos transitorios de red, se implementan cuatro capas complementarias de resiliencia:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Android Power Policy: STANDBY_BUCKET_EXEMPTED (Bucket 5) │
│    + Batería "Sin restricciones" (Unrestricted)             │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 2. Termux Foreground Service: termux-wake-lock              │
│    Mantiene CPU activa y sockets abiertos con pantalla off  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 3. Self-Healing Watchdog: ~/bin/termux-sshd-watchdog.sh     │
│    Verifica sshd cada 5s (nanosleep, 0% CPU, lock flock)    │
│    Auto-reinicia sshd y reasigna wake-lock si cae (<15s)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 4. Supervisión y Boot:                                      │
│    - Cron fallback (* * * * * supervisor watchdog)          │
│    - Termux:Boot (~/.termux/boot/start_sshd.sh)             │
└─────────────────────────────────────────────────────────────┘
```

### Componentes de Auto-Recuperación:
1. **Política de Batería Android**: `com.termux` y `com.termux.boot` configurados con optimización de batería en modo "Sin restricciones" (Standby Bucket 5 `STANDBY_BUCKET_EXEMPTED`).
2. **Wake-Lock Continuo**: `termux-wake-lock` mantiene el servicio en primer plano (`com.termux.service_wake_lock`) evitando que Android suspenda la CPU o cierre sockets TCP al apagar la pantalla.
3. **Watchdog de Proceso SSHD (`~/bin/termux-sshd-watchdog.sh`)**:
   - Idempotente mediante descriptor de archivo y exclusión mutua `flock` sobre `/data/data/com.termux/files/usr/tmp/sshd_watchdog.lock`.
   - Bucle de sondeo pasivo cada 5 segundos vía llamada al sistema `nanosleep` (consumo medido: **0% CPU**, 00:00:00 de tiempo de CPU acumulado).
   - Ante la caída de `sshd`, detecta la ausencia, adquiere el wake-lock y reinicia `sshd` de inmediato, registrando el evento con marca temporal en `~/.termux/sshd_watchdog.log`.
   - Recuperación comprobada en prueba de kill destructiva: `SSHD_RECOVERY_TIME: 15.24s`, `MCP_TARGET_RECOVERY_TIME: 37.84s`.
4. **Supervisión por Cron**: Tarea programada en `crontab` que verifica cada minuto la existencia del proceso watchdog, restaurándolo si hubiese sido terminado.
5. **Persistencia en Reinicio**: `~/.termux/boot/start_sshd.sh` invocado automáticamente por la app `Termux:Boot` al inicio del sistema (`BOOT_COMPLETED`), levantando el wake-lock, `sshd`, `crond` y el watchdog.

---

## 4. Delimitación de Workspace y Pruebas de Seguridad

### Workspace Autorizado
- **Proyecto Canónico**: `MCP_Local`
- **Ruta Raíz Canónica**: `/data/data/com.termux/files/home/Projects/test/MCP_Local`
- **Capacidades**: Lectura (`read`) y Estado (`git_status`, `target_status`, `list_directory`). Escrituras (`write_file`) deshabilitadas por defecto por el kill switch del Core (`writes_enabled: false`).

### Controles de Seguridad Negativa y Aislamiento
- **Acceso Root / Escalada de Privilegios**: **DENEGADO**. La cuenta destino `u0_a435` carece de privilegios `sudo` y no existe binario `su`.
- **Protección de Rutas del Sistema Android**: SELinux y permisos UNIX bloquean cualquier intento de acceso a rutas fuera del sandbox de Termux (`/data/system`, `/data/data`, etc.).
- **Bloqueo Sintáctico y Canónico de Path Traversal**: El Policy Engine del Gateway MCP intercepta y bloquea fail-closed con `INVALID_PATH` cualquier intento de escape (`..`, `/abs`, symlinks cruzados).
- **Aislamiento Interno**: La cuenta `u0_a435` es monousuario para el entorno Termux. Secretos locales (como `.mcp-pi.local.env`) se resguardan con permisos `600` fuera de las raíces de proyectos compartidos.

---

## 5. Procedimiento de Revocación de Emergencia

Para cortar de forma inmediata el acceso desde la Raspberry Pi hacia el Target Worker:

1. **Opción 1: Revocación de Clave en el Worker (Permanente e Inmediata)**
   Eliminar la clave del Gateway en `~/.ssh/authorized_keys`:
   ```bash
   sed -i '/mcp-gateway@MCP-Pi/d' ~/.ssh/authorized_keys
   ```
   *Efecto*: Todo intento de conexión SSH desde `MCP-Pi` es rechazado con `Permission denied (publickey)`.

2. **Opción 2: Deshabilitación del Target en el Gateway Core**
   Ejecutar en `MCP-Pi`:
   ```bash
   sudo -u mcp-gateway sqlite3 /home/mcp-gateway/.local/share/mcp-gateway/gateway.db \
     "UPDATE targets SET enabled=0, updated_at=datetime('now') WHERE id='termux-main';"
   ```
   *Efecto*: El Core del Gateway deniega fail-closed toda solicitud hacia `termux-main` con `TARGET_DISABLED`.

3. **Opción 3: Detención del Servicio SSHD y Watchdog en el Worker**
   ```bash
   pkill -f termux-sshd-watchdog.sh
   pkill -x sshd
   ```
