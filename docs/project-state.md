# Estado Operacional del Proyecto - MCP Raspberry Pi Gateway

Documento de seguimiento continuo y estado de componentes del sistema.

---

## 1. Matriz de Verificación Operacional

| Componente / Verificación | Estado | Detalle / Evidencia |
|---|---|---|
| **Raspberry identificada** | **PASS** | BCM2835, Model A+ Rev 1.1, ARMv6l (`MCP-Pi`) en `192.168.68.85` |
| **Hostname & Colisión** | **PASS** | Hostname establecido en `MCP-Pi`. Colisión con Pi-hole (`YorPi`) resuelta. |
| **SSH Administrativo** | **PASS** | OpenSSH 8.4p1 activo en puerto 22 (`Yorologo@192.168.68.85`) |
| **Identidad Técnica Pi** | **PASS** | Usuario `mcp-gateway` creado (UID 1001, sin sudo, sin login por password) |
| **Clave Dedicada Gateway** | **PASS** | Clave Ed25519 generada en `~/.ssh/mcp_gateway_ed25519` (privada 600, retenida en Pi) |
| **Hardware Pi** | **PASS** | CPU ARMv6l 700MHz, 176MB RAM SO, 14.5GB rootfs (12GB libres) |
| **MAC Pi** | **PASS** | Interfaz `wlan0`: `8c:90:2d:ac:e5:c0` (preservada tras reinicios) |
| **Wi-Fi Pi** | **PASS** | Adaptador RTL8188EUS con driver `r8188eu` estable (link quality 100/100) |
| **LAN / DNS / Internet** | **PASS** | Conectividad total validada post-reboot |
| **Pi-hole Reachability** | **PASS** | Ping a `192.168.68.54`: 0% pérdidas |
| **APT Update** | **PASS** | `apt update` completado al 100% sin errores de índices |
| **UPDATE_GATE** | **PASS** | 58 paquetes actualizables identificados |
| **SYSTEM_UPGRADE** | **DEFERRED** | Pospuesto para preservar estabilidad de driver Wi-Fi sin ethernet de respaldo |
| **Canal Pi → PC (`pc-local`)** | **PASS_WITH_LIMITATION** | Alias `pc-local` validado con Ed25519 sin password. Aislamiento limitado por sandbox monousuario Termux. |
| **Workspace de Prueba** | **PASS** | Lectura/escritura en `mcp-workspace-smoke/hello.txt` exitosa |
| **Aislamiento en PC** | **PASS_WITH_LIMITATION** | Non-root en Android 16 (`u:r:untrusted_app_27`), pero monousuario Termux |
| **Supervivencia a Reboot** | **PASS** | Canal Pi → PC restaurado y verificado tras reboot de `MCP-Pi` |
| **Revocación de Clave** | **PASS** | Prueba de revocación y restauración ejecutada con éxito |
| **Gateway Core (Fase 4A)** | **PASS** | Arquitectura multi-target, Python stdlib (cero dependencias externas), UID 1001 |
| **Remote Unit Tests** | **PASS** | 77/77 pruebas unitarias ejecutadas remotamente en `MCP-Pi` bajo `mcp-gateway` (126.3s en ARMv6l) |
| **Live Target Tests** | **PASS** | 8/8 herramientas verificadas en vivo contra `termux-main` (`health`, `list_targets`, `target_status`, `list_directory`, `file_stat`, `read_file`, `git_status`, `run_task`) tanto con backend JSON como con backend SQLite |
| **Policy Engine** | **PASS** | Deny-by-default, bloqueo sintáctico `..`, validación canónica remota con `realpath`, allowlist estricta de tareas |
| **Negative Security Tests** | **PASS** | 5/5 vectores bloqueados (`..`, `/abs`, `task`, `target`, escape de symlink fuera de root) |
| **Persistent Registry (Fase 4B)** | **PASS** | SQLite 3.34.1 con consultas 100% parametrizadas, `PRAGMA user_version = 1`, paridad total con JSON, rollback transparente (`MCP_GATEWAY_REGISTRY=json`) |
| **Emergency Kill Switch** | **PASS** | Interrupción global inmediata en SQLite (`gateway_enabled=false`) y por target individual (`TARGET_DISABLED`), validado en vivo |
| **Admin Console (Fase 4B)** | **PASS** | Flask 1.1.2 + Jinja2 + Tailwind CSS en `127.0.0.1:8080`, protegido por túnel SSH, CSRF, cookies HttpOnly/SameSite=Strict, PBKDF2 hashing, rate limiting (5 intentos / 60s) |
| **Servicio Admin systemd** | **PASS** | `mcp-gateway-admin.service` activo y habilitado en arranque bajo usuario `mcp-gateway` (PID 2691, RSS ~14.6MB, latencia ~50ms) |
| **Official Go MCP SDK (Fase 4C)** | **PASS** | `github.com/modelcontextprotocol/go-sdk` v1.7.0 fijado, protocolo 2026-07-28 (compat 2025-11-25), cross-compile estático ARMv6 (8.38MB) |
| **Transports MCP (Fase 4C)** | **PASS** | stdio (subproceso local) y Streamable HTTP en `127.0.0.1:8090/mcp` (stateless), 8/8 herramientas verificadas vía MCP |
| **Servicio MCP systemd** | **PASS** | `mcp-gateway-mcp.service` activo y habilitado en arranque bajo usuario `mcp-gateway` (PID 2720, RSS ~10MB) |
| **Seguridad E2E vía MCP** | **PASS** | 6/6 vectores negativos rechazados por Python Core (`INVALID_PATH`, `UNKNOWN_TARGET`, `UNKNOWN_PROJECT`, `TASK_NOT_ALLOWED`, `PATH_OUTSIDE_ALLOWED_ROOT`, `GATEWAY_DISABLED`) |
| **Integración ChatGPT** | **DEFERRED_TO_PHASE_6** | Conexión directa no permitida hacia localhost; requiere evaluar Secure MCP Tunnel en Fase 6 |

---

## 2. Parámetros del Canal Seguro Pi → PC y Gateway

- **Origen**: `mcp-gateway@MCP-Pi` (`192.168.68.85`, UID 1001, no sudo)
- **Destino (Target actual)**: `u0_a435@192.168.68.84:8022` (Alias: `pc-local` / `termux-local`, target ID: `termux-main`)
- **Autenticación**: Clave pública Ed25519 exclusiva (`mcp_gateway_ed25519`)
- **Host Fingerprint**: `SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`
- **Proyecto Autorizado**: `MCP_Local` -> `/data/data/com.termux/files/home/Projects/test/MCP_Local`
- **DHCP_RESERVATION**: `REQUIRED_MANUAL_ROUTER_ACTION` (Router DHCP para MAC `8c:90:2d:ac:e5:c0` -> `192.168.68.85`)
- **Consola de Administración**: `http://127.0.0.1:8080` (accesible exclusivamente mediante túnel SSH `ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85`)
- **Servidor MCP (Streamable HTTP)**: `http://127.0.0.1:8090/mcp` (confinado a loopback, servicio `mcp-gateway-mcp.service`)

---

## 3. Metadatos de Control

- **LAST_VERIFIED**: 2026-09-08 16:36 CST (22:36 UTC)
- **CURRENT_PHASE**: FASE 4C (Official MCP Protocol Adapter) - COMPLETADA
- **ROADMAP**:
  - **Fase 4C**: Official MCP Adapter (COMPLETADA)
  - **Fase 5**: Controlled Write (Siguiente)
  - **Fase 6**: External AI Clients
  - **Fase 7**: Stable Operations
- **NEXT_ACTION**: Implementar la Fase 5 (Controlled Write) permitiendo mutaciones seguras y auditadas en workspaces autorizados con validaciones estrictas y protección contra escrituras fuera de límites.
