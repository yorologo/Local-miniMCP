# Guía de Migración de Sistema Operativo — MCP-Pi Gateway

Este documento describe el procedimiento detallado, seguro y no destructivo para migrar la Raspberry Pi Model A+ desde Debian 11 (Bullseye) a la versión oficial **Raspberry Pi OS Lite 32-bit (Debian 13 Trixie)**, preservando el rollback físico de la tarjeta microSD original.

---

## 1. Principio Fundamental: Rollback Físico Garantizado

> [!IMPORTANT]
> **NO REALIZAR `apt full-upgrade` EN LA TARJETA ACTUAL**:
> - La tarjeta microSD en uso con Bullseye es el **KNOWN_GOOD_PHYSICAL_ROLLBACK**.
> - La migración se efectúa grabando una **segunda tarjeta microSD**.
> - En caso de cualquier anomalía de hardware, kernel o Wi-Fi, basta con apagar el equipo, reinsertar la tarjeta original y encenderlo para restaurar el servicio en menos de 2 minutos.

---

## 2. Imágenes Oficiales de Sistema Operativo

### Candidato Primario: Debian 13 (Trixie) 32-bit Lite
- **Nombre**: `Raspberry Pi OS Lite (32-bit)`
- **Distribución base**: Debian 13 (Trixie)
- **Entorno**: Headless (sin escritorio gráfico, CLI puro)
- **Compatibilidad**: Dispositivos `pi1-32bit` (ARMv6, SoC BCM2835)
- **URL oficial**: `https://downloads.raspberrypi.com/raspios_lite_armhf/images/raspios_lite_armhf-2026-06-19/2026-06-18-raspios-trixie-armhf-lite.img.xz`
- **SHA256**: `235aae6e32f40eb294b6485f99232d9ea5b6ee0251c8dc40e370177fac4754c2`

### Candidato Fallback: Debian 12 (Bookworm) 32-bit Legacy Lite
*(Utilizar únicamente si Trixie presenta un blocker de hardware real en el driver Wi-Fi `r8188eu`)*
- **Nombre**: `Raspberry Pi OS (Legacy, 32-bit) Lite`
- **Distribución base**: Debian 12 (Bookworm)
- **URL oficial**: `https://downloads.raspberrypi.com/raspios_oldstable_lite_armhf/images/raspios_oldstable_lite_armhf-2026-06-19/2026-06-18-raspios-bookworm-armhf-lite.img.xz`
- **SHA256**: `494db22e6f0f652e97fe6ed5c89fa51810f2abfa5afe6bcb422c6517d7aacd24`

---

## 3. Preparación de la Nueva MicroSD con Raspberry Pi Imager

En la estación de trabajo (PC):

1. **Abrir Raspberry Pi Imager**:
   - **Dispositivo**: `Raspberry Pi 1 / Zero`
   - **Sistema Operativo**: `Raspberry Pi OS (other)` -> `Raspberry Pi OS Lite (32-bit)` (o seleccionar la imagen descargada `2026-06-18-raspios-trixie-armhf-lite.img.xz`).
   - **Almacenamiento**: Seleccionar la nueva tarjeta microSD.
2. **Personalización del SO (engranaje de ajustes)**:
   - **Hostname**: `MCP-Pi`
   - **Usuario**: `Yorologo`
   - **Contraseña**: La contraseña operativa del entorno local
   - **Configurar Wi-Fi**:
     - SSID y contraseña de la red local Wi-Fi
     - País: Tu código de país correspondiente
   - **Servicios**:
     - Habilitar SSH -> Autenticación por clave pública Ed25519 (`~/.ssh/id_ed25519.pub`) y/o contraseña de respaldo
   - **Zona Horaria y Teclado**: Configurar según región local.
3. **Grabar y Verificar**:
   - Ejecutar la escritura y verificación en la nueva tarjeta.

---

## 4. Primer Arranque y Validación de Hardware

1. Extraer con seguridad la tarjeta microSD antigua de la Raspberry Pi Model A+ y guardarla en un estuche seguro.
2. Insertar la nueva tarjeta microSD en la Pi y conectar la alimentación.
3. Esperar aproximadamente 2-3 minutos mientras se expande el sistema de archivos y se asocia a la red Wi-Fi.
4. **Verificar Asignación de IP**:
   - El router debe asignarle la IP reservada `192.168.68.85` (asociada a la MAC `8c:90:2d:ac:e5:c0` del adaptador USB Wi-Fi RTL8188EUS).
5. **Comprobar Acceso Administrativo Inicial (Bootstrap Aislado)**:
   > [!IMPORTANT]
   > **PROHIBIDO EL USO DE `StrictHostKeyChecking=no` Y PROHIBIDA LA MODIFICACIÓN DE `known_hosts` GLOBAL**:
   > Para el primer inicio bajo control físico directo, utilizar un archivo temporal dedicado y aislado `~/.ssh/mcp_bootstrap_known_hosts`:
   ```bash
   ssh -o UserKnownHostsFile=~/.ssh/mcp_bootstrap_known_hosts Yorologo@192.168.68.85 "hostname"
   ```

---

## 5. Restauración de la Identidad SSH del Host (Host Key Pinning)

Para mantener la confianza inmutable de los clientes (`~/.ssh/mcp_known_hosts`), restauramos la clave de host Ed25519 original:

Desde la estación de trabajo con la bóveda de respaldo `~/.mcp_migration_backup/`:
```bash
# 1. Copiar las claves de host originales a la Pi usando el archivo de bootstrap
scp -o UserKnownHostsFile=~/.ssh/mcp_bootstrap_known_hosts ~/.mcp_migration_backup/ssh_host_ed25519_key* Yorologo@192.168.68.85:/tmp/

# 2. En la Pi: instalar con permisos estrictos y reiniciar sshd
ssh -o UserKnownHostsFile=~/.ssh/mcp_bootstrap_known_hosts Yorologo@192.168.68.85 << 'EOF'
sudo cp /tmp/ssh_host_ed25519_key* /etc/ssh/
sudo chown root:root /etc/ssh/ssh_host_ed25519_key*
sudo chmod 600 /etc/ssh/ssh_host_ed25519_key
sudo chmod 644 /etc/ssh/ssh_host_ed25519_key.pub
sudo rm -f /tmp/ssh_host_ed25519_key*
sudo systemctl restart ssh
EOF

# 3. Eliminar inmediatamente el archivo temporal de bootstrap
rm -f ~/.ssh/mcp_bootstrap_known_hosts
```

### Verificación de Fingerprint y Conexión Permanente
En la estación de trabajo:
```bash
ssh-keygen -lf ~/.ssh/mcp_known_hosts
```
El fingerprint devuelto debe ser exactamente:
```text
SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E
```
Conectar utilizando estrictamente la clave fijada permanente:
```bash
ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/mcp_known_hosts Yorologo@192.168.68.85 "hostname"
```
Debe devolver `MCP-Pi` sin advertencias y sin alterar `known_hosts` global.

---

## 6. Instalación Limpia del Gateway e Idempotencia

1. Transferir el código fuente del proyecto a la Pi (o clonar mediante git):
   ```bash
   scp deploy_bundle.tar.gz Yorologo@192.168.68.85:/tmp/
   ssh Yorologo@192.168.68.85 "sudo mkdir -p /home/mcp-gateway/mcp-gateway && sudo tar -xzf /tmp/deploy_bundle.tar.gz -C /home/mcp-gateway/mcp-gateway"
   ```
2. Ejecutar la primera instalación:
   ```bash
   ssh Yorologo@192.168.68.85 "cd /home/mcp-gateway/mcp-gateway && sudo ./install.sh"
   ```
   **Resultado esperado**: `INSTALL_1: PASS`.
3. Ejecutar la segunda instalación inmediata:
   ```bash
   ssh Yorologo@192.168.68.85 "cd /home/mcp-gateway/mcp-gateway && sudo ./install.sh"
   ```
   **Resultado esperado**: `IDEMPOTENCY: PASS` (cero cambios destructivos, servicios recargados limpiamente).

---

## 7. Restauración del Estado del Gateway

Restaurar la base de datos persistente y las identidades de cliente desde la bóveda:

```bash
# Copiar backup a la Pi
scp ~/.mcp_migration_backup/gateway.db Yorologo@192.168.68.85:/tmp/
scp ~/.mcp_migration_backup/mcp_gateway_ed25519* Yorologo@192.168.68.85:/tmp/
scp ~/.mcp_migration_backup/authorized_keys Yorologo@192.168.68.85:/tmp/

# Restaurar archivos con propiedad mcp-gateway:mcp-gateway y permisos 600
ssh Yorologo@192.168.68.85 << 'EOF'
sudo cp /tmp/gateway.db /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
sudo cp /tmp/mcp_gateway_ed25519* /home/mcp-gateway/.ssh/
sudo cp /tmp/authorized_keys /home/mcp-gateway/.ssh/
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/.local/share/mcp-gateway /home/mcp-gateway/.ssh
sudo chmod 600 /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
sudo chmod 600 /home/mcp-gateway/.ssh/mcp_gateway_ed25519
sudo chmod 644 /home/mcp-gateway/.ssh/mcp_gateway_ed25519.pub
sudo chmod 600 /home/mcp-gateway/.ssh/authorized_keys
sudo rm -f /tmp/gateway.db /tmp/mcp_gateway_ed25519* /tmp/authorized_keys
sudo systemctl restart mcp-gateway-admin mcp-gateway-mcp
EOF
```

---

## 8. Verificación Integral de Aceptación

Ejecutar en la Pi:
```bash
sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway doctor
```
**Resultado obligatorio**: `OVERALL STATUS: HEALTHY` con 0 errores críticos.

Ejecutar desde la estación de trabajo:
- `python scripts/verify_phase_6a.py` (4/4 bloques PASS)
- `python scripts/verify_auth_precedence.py` (100% PASS)
- `& "C:\Program Files\Go\bin\go.exe" test -v ./...` (10/10 PASS)

---

## 9. Cierre Operacional de Phase 8 y Promoción a Línea Base de Producción

En fecha **10 de septiembre de 2026**, la modernización de sistema operativo hacia **Raspberry Pi OS Lite 32-bit (Debian 13 Trixie)** concluyó exitosamente todos los gates de validación técnica, funcional, de seguridad y de estabilidad en hardware real.

### 9.1 Matriz de Gates de Modernización (Phase 8)

| # | Gate Operativo | Estado | Evidencia Clave |
|---|---|---|---|
| 1 | Rescate pre-migración (USB Tethering) | **PASS** | `LOCAL_PHONE_RESCUE: PASS`: comunicación SSH Termux → MCP-Pi validada vía `usb0` sin dependencia de Wi-Fi (`MSI → Pi through phone NAT: NOT_AVAILABLE / NOT_REQUIRED`) |
| 2 | Arranque base Trixie y SO limpio | **PASS** | Kernel `6.18.34+rpt-rpi-v6 armv6l`, ext4 RW mount, zram swap (`/dev/zram0`). 0 failed units en systemd |
| 3 | RTL8188EUS Wi-Fi (`rtl8xxxu`) | **PASS** | `0bda:8179` enumerado, driver in-tree `rtl8xxxu`, `wlan0` en `192.168.68.85/22` |
| 4 | Independencia Wi-Fi y Estabilidad USB | **PASS** | Transferencia directa 37 MB: 0 desconexiones, 0 caídas, 0 USB resets (`HUB_PATH_STRONGLY_IMPLICATED_BY_A_B_EVIDENCE`) |
| 5 | Restauración Identidad SSH del Host | **PASS** | ED25519 `SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E` fijada con `StrictHostKeyChecking=yes` |
| 6 | Restauración Aplicación v1.0.1 | **PASS** | Binario oficial ARMv6 `bcaea3d5...`, SQLite integrity `ok`, usuario de servicio `mcp-gateway` (`UID: 102, GID: 105`, sin sudo) |
| 7 | Regresión Integral Funcional y Seguridad | **PASS** | Python: 107/107 PASS; Go: 10/10 PASS; Controlled Write: 19/19 PASS; Phase 6A: 4/4 PASS; Seguridad Negativa & Ingress: `SECURITY_GATE PASS` (8/8 canonical negatives + 3/3 ingress fail-closed); Tools: 8/8 PASS |
| 8 | Reboot Acceptance | **PASS** | `sudo sync && sudo reboot`: auto-reinicio, Admin PID 845, MCP PID 846, Doctor 19/19 HEALTHY |
| 9 | Formal 60-Minute Soak | **PASS** | 60 minutos continuos (12/12 muestras cada 5 min): 0 reinicios de servicios, 0 OOM, 0 caídas USB/Wi-Fi, probes T0/T30/T60 100% PASS |
| 10 | Promoción a Producción | **PASS** | Trixie promovido formalmente como **KNOWN_GOOD_PRODUCTION_BASELINE** |

### 9.2 Matriz Comparativa de Líneas Base (Bullseye vs Trixie)

| Métrica / Parámetro | Bullseye (Línea Base Histórica) | Trixie (Nueva Línea Base Producción) | Evaluación |
|---|---|---|---|
| **Distribución** | Raspbian 11 (Bullseye) 32-bit | Raspberry Pi OS 13 (Trixie) 32-bit | Moderna / Soporte activo |
| **Kernel** | `6.1.21+` (armv6l) | `6.18.34+rpt-rpi-v6` (armv6l) | Actualizado / Estable |
| **Driver RTL8188EUS** | `r8188eu` (staging) | `rtl8xxxu` (in-tree / `mac80211`) | In-tree, soporte nativo |
| **Python Runtime** | Python 3.9.2 | Python 3.13.5 | 100% compatible con stdlib Core |
| **Usuario de Servicio** | `mcp-gateway` (UID 1001, GID 1001, sin sudo) | `mcp-gateway` (UID 102, GID 105, sin sudo) | Mínimo privilegio preservado |
| **RAM Usable del SO** | ~176 MiB | ~173 MiB | Equivalente en hardware ARMv6 |
| **Mecanismo de Swap** | Swapfile en SD (`dphys-swapfile`, 99 MiB) | `zram` comprimido en RAM (`/dev/zram0`, 172 MiB) | Superior: elimina desgaste de microSD |
| **Consumo RSS / Memoria** | `NOT_DIRECTLY_COMPARABLE`<br>(v1 soak Bullseye: Admin ~6.3 MiB, MCP ~5.6 MiB, RAM disp ~92 MiB;<br>arranque Fase 4B/4C: Admin ~14.6 MiB, MCP ~10.0 MiB) | `NOT_DIRECTLY_COMPARABLE`<br>(Trixie post-soak: Admin ~10.7 - 11.1 MiB, MCP ~4.1 - 4.2 MiB, RAM disp ~71 - 73 MiB) | `Trixie resource fit: PASS`<br>Cero OOM, soak estable (60 min), margen operativo adecuado (>70 MiB libres) |
| **Temperatura SoC en reposo** | ~33 - 35 °C | ~33.6 - 34.2 °C | Térmica estable, throttled `0x0` |
| **Identidad Host SSH** | ED25519 `SHA256:wovttruok...` | ED25519 `SHA256:wovttruok...` | Identidad inmutable preservada |
| **Seguridad Negativa & Ingress** | `SECURITY_GATE PASS`<br>(7/7 tests negativos en v1 acceptance histórico) | `SECURITY_GATE PASS`<br>(8/8 canonical negatives + 3/3 ingress) | Semántica fail-closed preservada |
| **Software Gateway** | v1.0.1 (Commit `bcd8fe9...`) | v1.0.1 (Commit `bcd8fe9...`) | Cero cambios en código de aplicación |

---

## 10. Política de Retención del Rollback Físico

- La tarjeta microSD original con Debian 11 Bullseye permanece **etiquetada, protegida físicamente y PRESERVED AS KNOWN_GOOD_PHYSICAL_ROLLBACK UNTIL EXPLICIT DECOMMISSION DECISION**.
- Está **estrictamente prohibido sobrescribir o reutilizar** esa tarjeta microSD.
- Ante cualquier contingencia no recuperable en Trixie, el RTO para restaurar la línea base operativa original es **< 2 minutos** mediante swap físico de microSD.
