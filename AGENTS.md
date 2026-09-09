# AGENTS.md - Guía Operativa para Agentes Autónomos e IA

Este documento es la fuente de verdad y guía principal para cualquier IA o agente que trabaje en este repositorio. Cualquier agente nuevo que inicie sesión debe leer este archivo antes de realizar cualquier acción.

---

## 1. Propósito y Visión del Proyecto

Construir un **Gateway MCP personal** utilizando una **Raspberry Pi Model A+**.

### Arquitectura Conceptual
```text
+-------------------+
|      ChatGPT      |
+-------------------+
          |
          | MCP Seguro (Model Context Protocol)
          v
+-------------------+
|  Raspberry Pi A+  |  --> Frontera de seguridad / Orquestador / Gateway
+-------------------+
          |
          | SSH / SFTP auditado
          v
+-------------------+
|   Target Worker   |  --> Cómputo y almacenamiento pesado
+-------------------+
```

### División de Roles
- **Raspberry Pi A+**:
  - `valida`
  - `autoriza`
  - `limita`
  - `orquesta`
  - `audita`
  - **RESTRICCIÓN CLAVE**: La Raspberry Pi **NO** ejecutará modelos LLM ni cargas pesadas (CPU ARMv6 single-core, ~176 MB RAM utilizables).
- **Target Worker**:
  - `almacena`
  - `busca`
  - `compila`
  - `ejecuta`
  - `procesa`

---

## 2. Principios de Diseño Obligatorios

- **KISS (Keep It Simple, Stupid)**: Soluciones mínimas, nativas y directas.
- **Mínimo Privilegio**: Cuentas dedicadas con permisos acotados.
- **Deny-by-default**: Todo lo que no esté explícitamente autorizado se deniega.
- **Cambios pequeños**: Un solo cambio a la vez, verificado inmediatamente.
- **Pruebas después de cada cambio**: Evidencia antes de confirmación.
- **No shell arbitrario inicialmente**: El gateway expondrá herramientas de alto nivel acotadas, no ejecución ciega de comandos en shell.
- **No Docker salvo necesidad demostrada**: No aplica a la arquitectura ARMv6 por restricciones de memoria y soporte.
- **No exponer SSH a Internet**: El puerto 22 se mantiene exclusivamente dentro de la LAN.
- **No modificar la Raspberry Pi-hole**: Protección absoluta de la infraestructura de red preexistente.

---

## 3. Especificaciones de la Raspberry Pi Objetivo

Valores verificados y confirmados tras Fase 2A:
- **Dirección IPv4**: `192.168.68.85`
- **Dirección MAC**: `8c:90:2d:ac:e5:c0`
- **Hostname actual**: `MCP-Pi` (anteriormente `YorPi`)
- **Modelo de hardware**: `Raspberry Pi Model A Plus Rev 1.1` (SoC BCM2835)
- **Arquitectura de CPU**: `armv6l` (ARMv6-compatible processor rev 7)
- **Memoria RAM**: `176 MiB` utilizables (de 256 MB físicos compartidos con GPU)
- **Swap**: `100 MiB` en `/var/swap`
- **Sistema Operativo**: `Raspbian GNU/Linux 11 (bullseye)` 32-bit
- **Kernel**: `Linux MCP-Pi 6.1.21+ #1642 Mon Apr 3 17:19:14 BST 2023 armv6l`
- **Puerto SSH**: `22`
- **Usuario SSH**: `Yorologo` (sudoer con NOPASSWD)
- **Interfaz de red activa**: `wlan0` (adaptador USB Wi-Fi Realtek RTL8188EUS, driver `r8188eu` sin alteraciones)

---

## 4. Conexión y Gestión de Credenciales

### Comando de Acceso
```bash
ssh Yorologo@192.168.68.85
```

### Gestión de Secretos
- **Credenciales locales**: Se encuentran almacenadas en el archivo local `.mcp-pi.local.env` (ignorado por Git, permisos `600`).
- **PROHIBICIÓN ESTRICTA**:
  - `DO NOT COMMIT` el archivo `.mcp-pi.local.env`.
  - **NUNCA** imprimir la contraseña en consola, logs, commits, PRs ni respuestas de texto.
  - La meta a medio plazo es reemplazar la contraseña por autenticación con clave SSH pública/privada dedicada.

---

## 5. Pi-hole y Resolución de Colisión de Hostname

- **Dirección IP de Pi-hole**: `192.168.68.54`
- **Hostname de Pi-hole**: `YorPi`
- **Función**: DNS y bloqueador de anuncios local.
- **Estado**: Dispositivo crítico e independiente, totalmente **FUERA DEL ALCANCE** de este proyecto. No reiniciar, no reconfigurar, no alterar.

> [!NOTE]
> **Colisión de Hostname RESUELTA**:
> - **Gateway**: `192.168.68.85` -> Hostname establecido como `MCP-Pi` (MAC `8c:90:2d:ac:e5:c0`).
> - **Pi-hole**: `192.168.68.54` -> Conserva su identidad histórica `YorPi`.
> Ya no existe ambigüedad de nombres en la red local.

---

## 6. Estado Actual del Proyecto

- **Fase 1 (Línea Base Técnica y Diagnóstico)**: **TERMINADA**.
- **Fase 2A (Identidad de Red, Estabilidad y Recuperación del UPDATE_GATE)**: **TERMINADA**.
- **Fase 2B (Identidad Técnica en Gateway)**: **TERMINADA**.
  - Usuario `mcp-gateway` (UID 1001, sin sudo) creado con clave exclusiva Ed25519.
- **Fase 3 (Canal Seguro Pi → PC)**: **TERMINADA (PASS_WITH_LIMITATION)**.
  - Alias `pc-local` y `termux-local` configurados y validados sin contraseña desde `mcp-gateway`.
  - Workspace smoke probado con lectura/escritura (`mcp-workspace-smoke/hello.txt`).
  - Pruebas negativas y supervivencia tras reinicio de la Raspberry verificadas al 100%.
  - Limitación: entorno monousuario Android/Termux sin separación POSIX de usuarios.
  - Runbook detallado disponible en [docs/runbooks/pi-to-pc-ssh.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/pi-to-pc-ssh.md).
- **Fase 4A (Gateway Core)**: **TERMINADA**.
  - Núcleo del Gateway implementado en Python 3 stdlib puro (cero dependencias externas).
  - Ejecución bajo cuenta `mcp-gateway` (UID 1001, sin sudo).
  - Arquitectura multi-target y multi-proyecto desacoplada de la plataforma.
  - Políticas de seguridad deny-by-default (traversal bloqueado, resolución canónica remota con `realpath`, lista blanca estricta de tareas).
  - 8 herramientas implementadas y operativas (`health`, `list_targets`, `target_status`, `list_directory`, `file_stat`, `read_file`, `git_status`, `run_task`).
  - Verificación exhaustiva: 28/28 unit tests remotos, 8/8 live tests y 5/5 negative tests superados.
  - `MCP_SDK_GATE: DEFERRED`.
  - Documentación completa en [docs/gateway-mvp.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/gateway-mvp.md) y runbook en [docs/runbooks/gateway-smoke-test.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/gateway-smoke-test.md).
- **Fase 4B (Consola de Administración Segura & Registro Persistente)**: **TERMINADA**.
  - Registro SQLite (`gateway.db`, 64 KB) con esquema parametrizado (`PRAGMA user_version = 1`), soporte para rollback instantáneo a JSON (`MCP_GATEWAY_REGISTRY=json`).
  - Emergency Kill Switch global y por target verificado en vivo.
  - Consola web Flask 1.1.2 + Jinja2 + Tailwind CSS precompilado (17 KB) sirviendo exclusivamente en `127.0.0.1:8080`.
  - Acceso seguro mediante túnel SSH (`ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85`).
  - Servicio systemd `mcp-gateway-admin.service` activo y habilitado en arranque bajo usuario `mcp-gateway` (RSS ~19 MB, latencia ~50 ms).
  - Herramienta administrativa `mcp_gateway.admin_cli` (set-password, backup online vía SQLite API, export-json saneado, import-json).
  - Batería de pruebas: 71/71 unit tests remotos, 8/8 live tests, 5/5 negative security tests y ciclo completo de kill switch superados.
- **Fase 4C (Adaptador de Protocolo MCP Oficial)**: **TERMINADA**.
  - Adaptador de protocolo MCP basado en el SDK oficial de Go (`github.com/modelcontextprotocol/go-sdk` v1.7.0).
  - Binario estático optimizado cross-compilado para ARMv6 (`mcp-gateway-adapter`, 8.38 MB).
  - Protocolo MCP 2026-07-28 (compatible con negociación 2025-11-25).
  - Transportes soportados: stdio y Streamable HTTP (`127.0.0.1:8090/mcp` con chunked SSE).
  - Puente CLI `mcp_gateway.bridge` que preserva el 100% de la autoridad de seguridad, SQLiteRegistry y Policy Engine en Python.
  - Servicio systemd `mcp-gateway-mcp.service` activo y habilitado en arranque bajo usuario `mcp-gateway` (RSS ~10 MB).
  - Pruebas superadas: 77 unit tests, 8/8 herramientas MCP operativas en vivo, 8 negative/control cases DENIED y Kill Switch funcional.
  - Documentación en [docs/mcp-adapter.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/mcp-adapter.md) y runbook en [docs/runbooks/mcp-smoke-test.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/mcp-smoke-test.md).
- **Fase 5 (Operaciones de Escritura Controlada)**: **TERMINADA**.
  - Capacidad de mutación controlada `write_file` operativa y verificada.
  - Toda autoridad de seguridad permanece en Python Gateway Core (Go adapter actúa estrictamente como puente de protocolo).
  - 9 herramientas MCP expuestas vía stdio y Streamable HTTP (`127.0.0.1:8090/mcp`).
  - Reemplazo atómico remoto con preservación de modo, fsync y verificación estricta de hash (`expected_sha256`) contra condiciones de carrera / TOCTOU.
  - Modo simulación sin mutación (`dry_run=true`) con generación de diffs unificados en memoria.
  - Política de doble autorización deny-by-default: `writes_enabled == true` (global) AND `project.write == true` (proyecto).
  - Controles en Admin Console: Botón de pánico `/settings/disable-writes` (bloquea escrituras de inmediato preservando lecturas al 100%) y switches individuales por proyecto.
  - Respaldos automáticos en Gateway (`~/.local/share/mcp-gateway/backups/...`, retención rodante de hasta 5 versiones).
  - `APPLY_PATCH: DEFERRED_FOR_SAFE_IMPLEMENTATION` (KISS y seguridad determinista).
  - Batería de pruebas: 88/88 unit tests remotos en MCP-Pi, 19/19 pruebas E2E en vivo (dry run, hash lock, creación, symlink blocks, traversal blocks, size limits, NUL bytes, pánico, MCP HTTP protocol y recuperación).
  - Documentación en [docs/controlled-write.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/controlled-write.md) y runbooks en [docs/runbooks/controlled-write-smoke-test.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/controlled-write-smoke-test.md) y [docs/runbooks/write-recovery.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/write-recovery.md).
- **Fase 4D (Compatibilidad, Seguridad & Fundación del Ciclo de Vida)**: **TERMINADA**.
  - Versionado de contratos estricto (`compatibility.json`, Gateway v0.6.0, Core API v1, Bridge API v1, Tool Catalog v2 con 9 herramientas, Schema v1, MCP 2026-07-28 con Go SDK v1.7.0).
  - Fallo seguro fail-closed: adaptador MCP rechaza invocaciones si la versión del bridge o runtime no es compatible.
  - Trazabilidad de extremo a extremo con `request_id` propagado desde MCP hasta SSH y registro de auditoría SQLite.
  - Protección perimetral HTTP: filtrado estricto de cabecera `Host` (loopback exclusivo contra DNS rebinding) y `Origin` (HTTP 403 ante dominios no autorizados), con límite de cuerpo de 1 MiB.
  - Modelo de salud HTTP multicapa: `/live`, `/ready`, `/health`, y `/server/discover`.
  - Costura de autorización futura `can_client_use_tool(client_id, tool_name, registry)`.
  - Herramienta de diagnóstico y reparación segura (`doctor` y `repair`).
  - CLI unificado portátil [`bin/mcp-gateway`](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/bin/mcp-gateway).
  - Manifiesto de release [`manifest.json`](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/manifest.json) y sumas [`SHA256SUMS`](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/SHA256SUMS).
  - Instalador idempotente [`install.sh`](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/install.sh).
  - Panel administrativo web `/maintenance` con HTMX local (diagnóstico en tiempo real, respaldos online y rollback).
  - Batería de pruebas: 102/102 unit tests remotos en MCP-Pi, 6/6 Go tests, 19/19 E2E write regression tests y probes HTTP de seguridad superados.
  - Documentación en [docs/compatibility.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/compatibility.md), [docs/lifecycle.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/lifecycle.md) y runbooks en [docs/runbooks/doctor.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/doctor.md), [docs/runbooks/install.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/install.md), [docs/runbooks/update-rollback.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/update-rollback.md) y [docs/runbooks/uninstall.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/uninstall.md).
- **Fase 6A (Clientes AI Locales, Identidad & Grants - Official MCP Unification & Security Closure)**: **TERMINADA (PASS)**.
  - **Unificación MCP Oficial**: Cero implementaciones duplicadas. Servidor Python `stdio_server.py` eliminado por completo. Toda la capa de protocolo MCP (stdio y Streamable HTTP) reside exclusivamente en el binario estático Go (`mcp-gateway-adapter`) basado en `github.com/modelcontextprotocol/go-sdk` v1.7.0 (MCP 2026-07-28 / 2025-11-25).
  - **SSH Host Key Pinning Inmutable**: Clave de host pública Ed25519 de MCP-Pi (`SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E`) fijada en `~/.ssh/mcp_known_hosts`. Configuraciones forzadas con `StrictHostKeyChecking=yes`. Rechazo fail-closed comprobado ante clave adulterada (exit 255).
  - **Detección y Clasificación Honesta**: Gemini CLI y Claude Desktop clasificados como `NOT_INSTALLED`. Cliente activo en sesión: `ANTIGRAVITY`. Configuraciones generadas listas en `~/.gemini/config/mcp_config.json` y `%APPDATA%\Claude\claude_desktop_config.json`.
  - **Separación de Precedencia de Autorización**: El motor de políticas separa estrictamente la evaluación de grants de cliente (`TOOL_NOT_ALLOWED`) de los interruptores de seguridad operacional (`WRITES_DISABLED`). Un cliente sin grant nunca recibe filtración de información sobre el estado de switches de bajo nivel.
  - **Verificación de Ciclo de Vida**: `mcp-gateway setup` y `mcp-gateway update --check` verificados de forma no destructiva con manifiesto y sumas criptográficas `SHA256SUMS` íntegras.
  - **MCP 2026 Native Closure**: Streamable HTTP validado en `127.0.0.1:8090/server/discover` (200 OK) y `POST /mcp` con cabecera `Stateless: true` (200 OK con SSE chunked).
  - **Batería de Pruebas**: 107/107 unit tests locales, 107/107 unit tests remotos en MCP-Pi, 10/10 Go tests, suite en vivo de clientes 4/4 bloques aprobados, y doctor HEALTHY.
  - Documentación en [docs/ai-clients.md](file:///c:/Users/esaud/OneDrive/Escritorio/Proyectos/Local-miniMCP/docs/ai-clients.md), [docs/client-grants.md](file:///c:/Users/esaud/OneDrive/Escritorio/Proyectos/Local-miniMCP/docs/client-grants.md), [docs/chatgpt-gate.md](file:///c:/Users/esaud/OneDrive/Escritorio/Proyectos/Local-miniMCP/docs/chatgpt-gate.md), y runbooks asociados.
- **Fase 6B (Clientes AI Cloud & Gate de Integración ChatGPT)**: **SIGUIENTE**.
- **Fase 7 (Operación Estable & Resiliencia)**: *Futura*.

---

## 7. Mapa Rápido de Identidades Operacionales

```text
Pi (Gateway):
  Hostname: MCP-Pi
  IP: 192.168.68.85
  MAC: 8c:90:2d:ac:e5:c0
  Administrative access: ssh Yorologo@192.168.68.85
  Service identity: mcp-gateway (UID 1001, NO sudo)
  Web Admin Service: mcp-gateway-admin.service (127.0.0.1:8080)
  Web Admin Access: ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85
  MCP Protocol Service: mcp-gateway-mcp.service (127.0.0.1:8090)
  MCP Protocol Endpoint: http://127.0.0.1:8090/mcp (Streamable HTTP)

PC (Worker):
  Hostname: localhost
  LAN IP: 192.168.68.84
  Port: 8022
  Service identity: u0_a435 (Android 16 / Termux sandbox, NO root)

Pi → PC:
  Comando: ssh pc-local <comando>
  Allowed initial root: /data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-workspace-smoke
```

> [!IMPORTANT]
> **DIRECTIVAS OBLIGATORIAS DE SEGURIDAD**:
> - **DO NOT USE `Yorologo` FOR MCP OPERATIONS**: Las herramientas y llamadas MCP operan estrictamente como `mcp-gateway`.
> - **DO NOT EXPOSE 127.0.0.1:8080 OR 127.0.0.1:8090 TO LAN**: La consola web y el servidor MCP se mantienen confinados a localhost.
> - **DO NOT USE ADMINISTRATOR ACCOUNT ON PC**: El worker en el PC opera sin permisos elevados.
> - **DO NOT MODIFY `192.168.68.54`**: Pi-hole permanece estrictamente intocable.

---

## 8. Reglas Inmutables para Futuros Agentes

1. **Leer `AGENTS.md`** antes de cualquier intervención.
2. **Consultar [docs/project-state.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/project-state.md)** para conocer el estado actual y la siguiente acción autorizada.
3. **Verificar identidad del host** (`hostname -I`, `/proc/device-tree/model`) antes de aplicar cambios administrativos.
4. **No modificar `192.168.68.54`** bajo ninguna circunstancia.
5. **No revelar secretos** ni contraseñas en código, consola, commits ni documentación.
6. **No instalar componentes innecesarios**: Mantener la Pi extremadamente ligera. No instalar Docker ni software pesado.
7. **Ejecutar pruebas tras cambios**: Siempre verificar conectividad, servicios y recursos tras modificar cualquier archivo o servicio.
8. **Actualizar la documentación**: Cualquier cambio de infraestructura debe reflejarse de inmediato en `docs/project-state.md` y archivos relacionados.
9. **Preferir operaciones explícitas**: No ejecutar scripts ciegos ni comandos destructivos; verificar individualmente.
10. **Detenerse ante discrepancias**: Si la IP, MAC, modelo o respuesta del host no coincide con los valores registrados, ejecutar `STOP` de inmediato y documentar la anomalía.

