# ChatGPT Integration Gate & Secure MCP Tunnel Architecture

## 1. Contexto y Estado del Gate

- **Estado del Gate**: `LOCAL_SIDE_READY / OPENAI_PRODUCT_GATE_PENDING`
- **Veredicto**: `LOCAL_PASS` (Infraestructura local del Gateway 100% instalada, asegurada y verificada)
- **Invariante de Seguridad**: `NO INBOUND EXPOSURE` (Cero puertos entrantes abiertos en router, firewall o Raspberry Pi)
- **Transporte**: Official Outbound-only OpenAI Secure MCP Tunnel (`github.com/openai/tunnel-client`)
- **Cliente Registrado**: `chatgpt-main` (Protocolo `mcp-tunnel-2026-07-28`)
- **Grants Asignados**:
  - `termux-main:MCP_Local` (capacidad `read`)
  - `*.*` (capacidad `admin` para herramientas seguras de administración del appliance)
- **Servicio systemd**: `mcp-gateway-tunnel.service` (con `ExecCondition` guard fail-safe)
- **Endpoint MCP Local**: `127.0.0.1:8090/mcp` (Go Adapter, Streamable HTTP / SSE)
- **Endpoint Admin Local**: `127.0.0.1:8080` (Python Web Console)

---

## 2. Razón Fundamental de la Arquitectura

La Raspberry Pi Model A+ cuenta con especificaciones de hardware acotadas (ARMv6 BCM2835, ~173 MiB RAM, Wi-Fi USB). Exponer puertos entrantes directamente a Internet o mediante port-forwarding violaría el principio de **Deny by Default** y expondría la red privada local (incluyendo Pi-hole en `192.168.68.54`).

La solución arquitectónica adoptada cumple estrictamente con **KISS** y **Reuse First**:
1. **Outbound-Only Tunnel**: El cliente oficial `openai/tunnel-client` inicia una conexión saliente TLS segura hacia el plano de control de OpenAI (`tunnel.openai.com` / Cloudflare). No se abren puertos entrantes de ningún tipo en el router ni en la Raspberry Pi.
2. **Local Loopback Bridge**: El túnel redirige las peticiones entrantes de ChatGPT localmente a `http://127.0.0.1:8090/mcp`.
3. **Core Policy Enforcement**: Toda llamada es interceptada por el Go Adapter y validada contra el Core de Políticas de Python (`src/mcp_gateway/policy.py`) y SQLite Registry (`gateway.db`).
4. **Separación de Fallos**:
   - `LOCAL_MINIMCP_LIMITATION`: Ninguna. La compilación ARMv6, el cliente túnel, los permisos de servicio y las herramientas de administración están 100% operativas.
   - `OPENAI_PRODUCT_LIMITATION`: Cuando las credenciales del túnel no están aprovisionadas en `tunnel.env`, el servicio entra limpiamente en estado inactivo sin bucles de reinicio (`ExecCondition` exit code 2).

---

## 3. Componentes Implementados y Verificados

### 3.1 Binario Nativo ARMv6 `openai-tunnel-client`
- Repositorio oficial: `github.com/openai/tunnel-client`
- Adaptación para 32-bit: Corrección en `pkg/runtimeconfig/config.go` de cast `uint` a `uint64` para nanosegundos en arquitecturas de 32 bits (`armv6`).
- Compilación estática: Go 1.27 (`GOOS=linux GOARCH=arm GOARM=6`).
- Ubicación en MCP-Pi: `/usr/local/bin/openai-tunnel-client` (permisos 0755, root:root).

### 3.2 Servicio systemd `mcp-gateway-tunnel.service`
- Ubicación: `/etc/systemd/system/mcp-gateway-tunnel.service`
- Configuración: `/home/mcp-gateway/.config/mcp-gateway/tunnel.env` (permisos 0600, `mcp-gateway:mcp-gateway`).
- Guard de seguridad: `/usr/local/bin/mcp-gateway-tunnel-check`. Si `CONTROL_PLANE_TUNNEL_ID` o `CONTROL_PLANE_API_KEY` están vacías, `ExecCondition` retorna código 2, evitando que systemd intente arrancar el cliente en bucle.
- Dependencias: Inicia después de `mcp-gateway-mcp.service` y `network-online.target`.

### 3.3 Herramientas de Administración Segura del Appliance
Para permitir la operación del appliance sin shell arbitrario, se incorporaron 5 herramientas de alto nivel al catálogo MCP:
- `gateway_status`: Telemetría del appliance (CPU, RAM, zram, disco, temperatura, estado de servicios y base de datos).
- `gateway_doctor`: Diagnóstico unificado de 19 comprobaciones de integridad del sistema.
- `gateway_backup`: Generación segura de respaldos SQLite en caliente con hash lock.
- `gateway_maintenance`: Mantenimiento autónomo, verificación de integridad y rotación de backups.
- `gateway_reboot`: Reinicio seguro y programado del appliance (requiere `confirm: true`), mediado por script restringido `/usr/local/bin/mcp-gateway-reboot` sin sudo general.

---

## 4. Matriz de Seguridad y Aislamiento

| Vector / Control | Estado | Evidencia |
|---|---|---|
| Ingress Ports | PASS | 0 puertos expuestos a Internet / 0 puertos en router |
| Client Authentication | PASS | `chatgpt-main` mapeado en `ai_clients` con token / header seguro |
| Grants Authorization | PASS | Concesión explícita requerida para `tools/list` y `tools/call` |
| Appliance Administration | PASS | Solo clientes con capacidad `admin` pueden invocar `gateway_*` |
| Fail-Closed Protection | PASS | Peticiones anónimas o sin grant retornan error HTTP 401 / `TOOL_NOT_ALLOWED` |
| Host & Origin Ingress | PASS | Rebinding HTTP rechazado con 403 Forbidden |
| Reboot E2E Fire Test | PASS | Invocación MCP -> reboot -> auto-arranque -> Doctor 19/19 HEALTHY |

---

## 5. Procedimiento para Conectar ChatGPT (Aprovisionamiento)

Cuando se disponga de acceso al dashboard de túneles MCP en OpenAI:
1. Crear el túnel en el portal de OpenAI y obtener:
   - `TUNNEL_ID`
   - `API_KEY`
2. Editar `/home/mcp-gateway/.config/mcp-gateway/tunnel.env` en MCP-Pi:
   ```ini
   CONTROL_PLANE_API_KEY=tu_api_key_aqui
   CONTROL_PLANE_TUNNEL_ID=tu_tunnel_id_aqui
   MCP_SERVER_URL=http://127.0.0.1:8090/mcp
   HEALTH_LISTEN_ADDR=127.0.0.1:8091
   LOG_FILE=/home/mcp-gateway/.local/share/mcp-gateway/logs/tunnel-client.log
   LOG_LEVEL=info
   ```
3. Reiniciar el servicio:
   ```bash
   sudo systemctl restart mcp-gateway-tunnel.service
   ```
4. Verificar el enlace:
   ```bash
   systemctl status mcp-gateway-tunnel.service
   ```
