# Runbook: MCP Gateway Installation & Setup

Este runbook describe el proceso de instalación automatizada e idempotente del Gateway MCP en la Raspberry Pi.

---

## Prerrequisitos

- Host objetivo: Raspberry Pi Model A+ (`armv6l`) o dispositivo Linux compatible.
- Cuenta administrativa con privilegios `sudo`.
- Python 3.9+ instalado en el sistema.

---

## 1. Instalación Idempotente Automática

El script [`install.sh`](../../install.sh) realiza todo el despliegue de forma idempotente y segura:

```bash
# En MCP-Pi como usuario administrativo (`yorologo`):
sudo /home/mcp-gateway/mcp-gateway/install.sh
```

### Operaciones Realizadas por el Instalador
1. **Verificación de Entorno**: Valida que la arquitectura (`armv6l`, `aarch64`, etc.) y la versión de Python cumplan los requisitos.
2. **Usuario de Servicio**: Crea el usuario dedicado de sistema `mcp-gateway` con UID de sistema asignado por el OS, sin acceso sudo, si no existe.
3. **Directorios y Permisos**: Configura permisos estrictos (`0700` para datos y configuración, `0755` para ejecutables).
4. **Base de Datos**: Inicializa el esquema SQLite con `PRAGMA user_version = 1`.
5. **Servicios Systemd**: Instala y activa `mcp-gateway-admin.service` (`0.0.0.0:80`, accesible como `http://192.168.68.55`, LAN allowlisted) y `mcp-gateway-mcp.service` (`127.0.0.1:8090`, loopback).
6. **Binario CLI**: Instala el enlace simbólico global `/usr/local/bin/mcp-gateway`.

---

## 2. Verificación Post-Instalación

```bash
# 1. Comprobar servicios activos
systemctl status mcp-gateway-admin mcp-gateway-mcp

# 2. Comprobar salud con el CLI
sudo -u mcp-gateway mcp-gateway status
sudo -u mcp-gateway mcp-gateway doctor
```
