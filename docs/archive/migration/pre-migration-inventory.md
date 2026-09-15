# Pre-Migration Technical Inventory Snapshot (Phase 7)

**Fecha de captura**: 2026-09-09 14:15 CST (2026-09-09 20:15 UTC)  
**Host evaluado**: `MCP-Pi` (`192.168.68.85`)  
**Propósito**: Línea base física, de red, sistema operativo y servicios para migración no destructiva.

---

## 1. Hardware & Rendimiento

| Parámetro | Valor Verificado |
|---|---|
| **Modelo de Hardware** | `Raspberry Pi Model A Plus Rev 1.1` (SoC BCM2835) |
| **Arquitectura CPU** | `armv6l` (ARMv6-compatible processor rev 7 v6l, 1 core @ 700 MHz) |
| **Memoria RAM** | `176 MiB` utilizables por SO (compartida con GPU) |
| **Memoria Swap** | `99 MiB` en `/var/swap` |
| **Almacenamiento Rootfs** | `15 GB` microSD (2.2 GB ocupados, 12 GB libres, 16% uso) |
| **Alimentación / Bus USB** | Bus único USB 2.0 (`1d6b:0002 Linux Foundation 2.0 root hub`) |

---

## 2. Sistema Operativo & Software Base

| Componente | Versión Actual (Bullseye Baseline) |
|---|---|
| **Distribución** | `Raspbian GNU/Linux 11 (bullseye)` 32-bit |
| **Kernel** | `Linux MCP-Pi 6.1.21+ #1642 Mon Apr 3 17:19:14 BST 2023 armv6l` |
| **Python Runtime** | `Python 3.9.2` (`/usr/bin/python3`) |
| **SQLite Engine** | `SQLite 3.34.1` |
| **Flask Framework** | `1.1.2` (stdlib + Flask/Jinja2 mínimo para Admin Console) |
| **OpenSSH Server** | `OpenSSH_8.4p1 Raspbian-5+deb11u5, OpenSSL 1.1.1w` |
| **systemd Init** | `systemd 247 (247.3-7+rpi1+deb11u7)` |

---

## 3. Red & Conectividad Inalámbrica

| Parámetro | Valor Verificado |
|---|---|
| **Hostname** | `MCP-Pi` |
| **Dirección IPv4** | `192.168.68.85/22` (asignada vía DHCP con reserva) |
| **Dirección MAC** | `8c:90:2d:ac:e5:c0` (interfaz `wlan0`) |
| **Servidores DNS** | Primario: `192.168.68.54` (Pi-hole local `YorPi`), Secundario: `94.140.14.14` |
| **Adaptador USB Wi-Fi** | `Bus 001 Device 002: ID 0bda:8179 Realtek Semiconductor Corp. RTL8188EUS 802.11n` |
| **Módulos de Kernel Wi-Fi** | `r8188eu` (324 KB), `cfg80211` (816 KB), `rfkill` (23 KB), `libarc4` (1.7 KB) |
| **Interfaz Local Loopback** | `lo`: `127.0.0.1/8`, `::1/128` |

---

## 4. Servicios & Listeners de Red

### Servicios Activos
- **`mcp-gateway-admin.service`**:
  - Estado: `active (running)`
  - Endpoint: `127.0.0.1:8080` (HTTP Console con PBKDF2, CSRF y sesión HttpOnly)
  - Usuario: `mcp-gateway` (UID 1001)
  - Archivo unit: `/etc/systemd/system/mcp-gateway-admin.service`
- **`mcp-gateway-mcp.service`**:
  - Estado: `active (running)`
  - Endpoint: `127.0.0.1:8090/mcp` (Streamable HTTP, Go SDK v1.7.0, protocolo MCP 2026-07-28)
  - Binario: `/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter`
  - Usuario: `mcp-gateway` (UID 1001)
  - Archivo unit: `/etc/systemd/system/mcp-gateway-mcp.service`

### Listeners de Red (`ss -lntup`)
```text
Netid State  Local Address:Port   Peer Address:Port   Process / Notes
tcp   LISTEN 127.0.0.1:8090       0.0.0.0:*           mcp-gateway-adapter (MCP Streamable HTTP)
tcp   LISTEN 127.0.0.1:8080       0.0.0.0:*           python3 (Admin Console)
tcp   LISTEN 0.0.0.0:22           0.0.0.0:*           sshd (OpenSSH LAN)
tcp   LISTEN [::]:22              [::]:*              sshd (OpenSSH LAN)
```
> [!IMPORTANT]
> **Cero Puertos MCP Expuestos a LAN**: Los puertos 8080 y 8090 están estrictamente confinados a `127.0.0.1`.

---

## 5. Cuentas de Usuario y Estructura de Archivos

- **Cuenta Administrativa**: `Yorologo` (sudoer con NOPASSWD, acceso por clave Ed25519 `~/.ssh/id_ed25519`).
- **Cuenta de Servicio**: `mcp-gateway` (`uid=1001(mcp-gateway) gid=1001(mcp-gateway)`), sin sudo, shell restringido.
- **Ruta del Aplicativo**: `/home/mcp-gateway/mcp-gateway`
- **Base de Datos SQLite**: `/home/mcp-gateway/.local/share/mcp-gateway/gateway.db` (permisos 0600)
- **Directorio de Backups**: `/home/mcp-gateway/.local/share/mcp-gateway/backups/` (retención rotativa de hasta 5 versiones)
- **Configuración Local**: `/home/mcp-gateway/.config/mcp-gateway/`

---

## 6. Huellas Criptográficas & Claves SSH

| Clave | Archivo Remoto | Tipo | Fingerprint SHA256 | Estado en Clientes |
|---|---|---|---|---|
| **Host Key de MCP-Pi** | `/etc/ssh/ssh_host_ed25519_key.pub` | Ed25519 256-bit | `SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E` | **Fijada (pinned)** en `~/.ssh/mcp_known_hosts` en Windows con `StrictHostKeyChecking=yes` |
| **Gateway Target Identity** | `/home/mcp-gateway/.ssh/mcp_gateway_ed25519.pub` | Ed25519 256-bit | `SHA256:Vd61kRdCrV+JbNYnPyKPLVEQBi7xsQ24Dbug+epdMEY` | Autorizada en Target Worker (`termux-main`) |
| **Client Forced Command Wrapper** | `/home/mcp-gateway/.ssh/authorized_keys` | Multi-key | Claves dedicadas para `gemini-main` y `claude-desktop` | Invocan forzadamente `mcp-gateway-client-stdio <client_id>` |

---

## 7. Garantía de Rollback Físico

- **Tarjeta microSD actual**: Tarjeta física de 16 GB con instalación completa Bullseye funcional.
- **Estado**: Se retirará físicamente de la Raspberry Pi Model A+ y se conservará intacta como `KNOWN_GOOD_PHYSICAL_ROLLBACK`.
- **Tiempo de Rollback**: < 2 minutos (apagar, reinsertar tarjeta Bullseye, encender).
