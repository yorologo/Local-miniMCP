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
| **Remote Unit Tests** | **PASS** | 102/102 pruebas unitarias ejecutadas remotamente en `MCP-Pi` bajo `mcp-gateway` (suites: config, registry, schema, policy, tools, bridge, web_auth, web_security, web_views, cli, compatibility, doctor, lifecycle) |
| **Live Target Tests** | **PASS** | 9/9 herramientas verificadas en vivo contra `termux-main` (`health`, `list_targets`, `target_status`, `list_directory`, `file_stat`, `read_file`, `git_status`, `run_task`, `write_file`) |
| **Policy Engine** | **PASS** | Deny-by-default, bloqueo sintáctico `..`, validación canónica remota con `realpath`, allowlist estricta de tareas, validación estricta de rutas de escritura y UTF-8 |
| **Negative Security Tests** | **PASS** | 14/14 vectores negativos bloqueados (`..`, `/abs`, symlinks, symlink dir escape, non-UTF8, oversized, conflict, unauth target/project, etc.) |
| **Persistent Registry (Fase 4B)** | **PASS** | SQLite 3.34.1 con consultas 100% parametrizadas, `PRAGMA user_version = 1`, paridad total con JSON, rollback transparente (`MCP_GATEWAY_REGISTRY=json`) |
| **Emergency Kill Switch** | **PASS** | Interrupción global inmediata en SQLite (`gateway_enabled=false`) y por target individual (`TARGET_DISABLED`), validado en vivo |
| **Admin Console (Fase 4B)** | **PASS** | Flask 1.1.2 + Jinja2 + Tailwind CSS en `127.0.0.1:8080`, protegido por túnel SSH, CSRF, cookies HttpOnly/SameSite=Strict, PBKDF2 hashing, rate limiting |
| **Servicio Admin systemd** | **PASS** | `mcp-gateway-admin.service` activo y habilitado en arranque bajo usuario `mcp-gateway` (PID 2691, RSS ~14.6MB, latencia ~50ms) |
| **Official Go MCP SDK (Fase 4C)** | **PASS** | `github.com/modelcontextprotocol/go-sdk` v1.7.0 fijado, protocolo 2026-07-28 (compat 2025-11-25), cross-compile estático ARMv6 (8.78MB) |
| **Transports MCP (Fase 4C)** | **PASS** | stdio (subproceso local) y Streamable HTTP en `127.0.0.1:8090/mcp` (stateless), 9/9 herramientas verificadas vía MCP |
| **Servicio MCP systemd** | **PASS** | `mcp-gateway-mcp.service` activo y habilitado en arranque bajo usuario `mcp-gateway` (PID 4977, RSS ~10MB) con apagado graceful |
| **Controlled Write (Fase 5)** | **PASS** | Mutación atómica controlada con doble llave (`writes_enabled` AND `project.write`), hash lock precondicional `expected_sha256`, backups rotativos en Pi, dry-run unified diff |
| **Writes Panic Button (Fase 5)**| **PASS** | Bloqueo instantáneo de escrituras vía `/settings/disable-writes` manteniendo 100% disponibles las operaciones de lectura |
| **E2E Write Verification (Fase 5)**| **PASS** | 19/19 pruebas E2E superadas en vivo en `scripts/verify-phase-5.py` |
| **Contract Versioning (Fase 4D)** | **PASS** | Versionado explícito en `compatibility.json` (Gateway v1.0.1, Core v1, Bridge v1, Tools v2, Schema v1, MCP 2026-07-28 con fallback 2025-11-25) |
| **Fail-Closed Gate (Fase 4D)** | **PASS** | El adaptador Go valida versiones con el bridge al inicio y rechaza invocaciones si hay incompatibilidad (`ADAPTER_NOT_READY`, HTTP 503) |
| **Host & Origin Security (Fase 4D)** | **PASS** | Protección estricta contra DNS rebinding y spoofing HTTP: Host loopback exclusivo, Origin autorizado o nulo (403 Forbidden en otros casos), body limit 1 MiB |
| **Health Model & Probes (Fase 4D)** | **PASS** | `/live` (liveness), `/ready` (readiness fail-closed), `/health` (metadatos consolidados sin secretos), `/server/discover` (capacidades MCP) |
| **Doctor & Safe Repair (Fase 4D)** | **PASS** | Diagnóstico en 8 puntos con auto-reparación no destructiva de permisos y recargas |
| **Unified CLI (Fase 4D)** | **PASS** | Wrapper portátil `bin/mcp-gateway` implementando `status`, `doctor`, `repair`, `backup`, `restore`, `rollback`, `uninstall` |
| **Packaging & Manifest (Fase 4D)** | **PASS** | `manifest.json`, `SHA256SUMS`, script de instalación idempotente `install.sh` |
| **Web Maintenance & HTMX (Fase 4D)** | **PASS** | Panel `/maintenance` con HTMX local embebido (diagnósticos en vivo, respaldos online, rollback) |
| **apply_patch Tool** | **DEFERRED_FOR_SAFE_IMPLEMENTATION** | Pospuesto intencionalmente bajo KISS; `write_file` con `expected_sha256` provee edición segura atómica sin complejidad de parsing multi-hunk |
| **Local AI Clients (Fase 6A Closeout)** | **PASS** | Integración nativa de clientes (`gemini-main`, `claude-desktop`) sobre SSH stdio con claves Ed25519 dedicadas y forced command wrapper `bin/mcp-gateway-client-stdio`. Cero exposición LAN/Internet. |
| **Official MCP Unification (Fase 6A)** | **PASS** | Servidor stdio MCP JSON-RPC completamente unificado sobre el SDK Oficial de Go (`github.com/modelcontextprotocol/go-sdk` v1.7.0). Cero implementaciones duplicadas (`stdio_server.py` eliminado). Solo UNA implementación MCP activa. |
| **SSH Host Pinning & Security (Fase 6A)** | **PASS** | Clave pública Ed25519 fijada en `~/.ssh/mcp_known_hosts` (`SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E`). `StrictHostKeyChecking=yes` en configs de clientes. Fallo seguro probado (código 255 ante adulteración). |
| **Client Detection & Classification (Fase 6A)** | **PASS** | Gemini CLI y Claude Desktop clasificados verídicamente como `NOT_INSTALLED`. Cliente real en sesión: `ANTIGRAVITY`. Archivos de configuración redactados con pinning SSH. |
| **Authorization Precedence (Fase 6A)** | **PASS** | Separación estricta entre capa de autorización (`TOOL_NOT_ALLOWED` / unknown tool) e interruptor operativo (`WRITES_DISABLED`). Fuga de estado hacia clientes no autorizados prevenida al 100%. |
| **Lifecycle & Contracts (Fase 6A)** | **PASS** | `mcp-gateway setup` (Doctor HEALTHY) y `mcp-gateway update --check` (manifest y `SHA256SUMS` íntegros) validados de forma no destructiva. |
| **MCP 2026 Native Closure (Fase 6A)** | **PASS** | Streamable HTTP verificado in vivo: `/server/discover` (200 OK), `POST /mcp` con `Stateless=true` (200 OK con SSE chunked), negociación de protocolo 2026-07-28 / 2025-11-25. |
| **Dynamic Grants & Policy (Fase 6A)** | **PASS** | Catálogo dinámico `tools/list` e invocación `tools/call` sincronizados en tiempo real mediante middleware Go hacia Python Policy Engine. Aislamiento estricto: Gemini CLI (8 herramientas, sin escritura), Claude Desktop (7 herramientas lectura). |
| **Live Client Verification (Fase 6A)**| **PASS** | 4/4 suites de pruebas en vivo superadas al 100% en `scripts/verify_phase_6a.py` (baseline gemini, baseline claude, mutación dinámica de grants y emergency disable fail-closed). 107/107 unit tests locales y remotos pasados. 10/10 Go tests pasados. |
| **ChatGPT Gate** | **BLOCKED_BY_PRODUCT_CAPABILITY** | Endpoint Streamable HTTP retenido exclusivamente en `127.0.0.1:8090/mcp`. Cloudflare/ngrok/public exposure estrictamente bloqueados. |
| **Inventory & Baseline Freeze (Fase 7A)** | **PASS** | Inventario exhaustivo documentado en `docs/migration/pre-migration-inventory.md`. Git limpio en `ee23898`, tag `phase-6a-pass`. |
| **Backup Gate & Vault Fuera de Git (Fase 7A)**| **PASS** | `gateway.db` (86 KB, integridad verificada), export JSON, claves Ed25519 de host y target resguardadas en `~/.mcp_migration_backup/` con permisos 600. |
| **Physical Rollback Preservation (Fase 7A)** | **PASS** | MicroSD original Bullseye preservada intacta como `KNOWN_GOOD_PHYSICAL_ROLLBACK`. Procedimiento en `docs/runbooks/microsd-recovery.md` (RTO < 2 min). |
| **OS Candidate Evaluation (Fase 7A)** | **PASS** | Oficial Raspberry Pi OS Lite 32-bit (Debian 13 Trixie, `2026-06-18-raspios-trixie-armhf-lite.img.xz`) catalogado; Bookworm Legacy Lite como fallback. |
| **Target Worker Offline Resilience (Fase 7A)**| **PASS** | Ante worker desconectado (`192.168.68.84:8022`), gateway responde en 168 ms con `SSH_FAILED` estructurado, sin cuelgues ni corrupción. Doctor permanece `HEALTHY`. |
| **Runbooks & Contingencia (Fase 7A)** | **PASS** | Runbooks creados: `microsd-recovery.md`, `disaster-recovery.md`, `reboot-recovery.md`, `network-recovery.md`, `os-migration.md`, `v1-acceptance.md`. |
| **Physical Migration Trixie (Fase 7B)** | **DEFERRED_POST_V1** | Postpuesta formalmente post-v1.0 por decisión de arquitectura. La línea base operativa de producción para v1.0.0 es Raspbian 11 (Bullseye) sobre Raspberry Pi Model A+. |
| **Three-Way Source of Truth Audit** | **PASS** | Auditoría rigurosa superada: Local worktree == GitHub origin/develop == MCP-Pi deployment (31/31 archivos core idénticos bit a bit por SHA256). Bóveda privada verificada. Fresh clone reproducible al 100%. |
| **Rollback Fail-Closed** | **PASS** | `mcp-gateway rollback` sin versión previa rechaza fail-closed con código de salida 1 |
| **Rollback Functional Sandbox** | **PASS** | Ciclo completo probado en sandbox aislado (`/tmp/mcp_rollback_sandbox_*`): validación de candidato B, actualización de puntero `current`/`previous`, reversión exitosa a release A y cleanup |
| **Formal Bounded Soak** | **PASS** | Soak de 60 min completado: 0 caídas, 0 cuelgues, 0 reinicios inesperados, 0 fugas de memoria (Admin RSS 6.3MB, MCP RSS 5.6MB, RAM disponible 92.5MB), 0 errores USB/Wi-Fi |
| **Target Worker Offline Handling**| **PASS** | Degradación limpia ante target desconectado: respuesta rápida en 168 ms con `SSH_FAILED` estructurado sin bloqueos ni corrupción |
| **Target Worker Return Gate** | **PASS** | Reconexión dinámica validada en caliente a `192.168.68.72:8022` con `HostKeyAlias=termux-main` (`SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`). 5/5 operaciones operativas, Phase 5 live 19/19 superadas y Full Path validado. |
| **Network Interruption Gate** | **WAIVED_WITH_RATIONALE** | Reconexión Wi-Fi completamente demostrada por reboot real de hardware. Corte deliberado de interfaz inalámbrica dispensado para evitar bloqueo remoto sin consola física. |
| **Backup / Restore Sandbox** | **PASS** | Copia sandbox validada: integridad `ok`, `user_version = 1`, paridad exacta con base de datos de producción (1 target, 2 proyectos, 2 clientes AI, 2 grants, 8 settings) |
| **Security Negative Suite** | **PASS** | 7/7 vectores de seguridad bloqueados fail-closed en vivo (acceso anónimo 0 tools, tool desconocida, path traversal, escrituras deshabilitadas, Host rebinding 403, Origin 403, cliente no autorizado) |
| **Full Client Path** | **PASS** | Cadena completa validada: Cliente AI (gemini-main) -> SSH forced command -> Go MCP -> Python Core -> Target SSH -> termux-main |
| **Release Status v1.0.0** | **RELEASED** | Release formal v1.0.0 completado y publicado (commit `d52f848`, tag `v1.0.0`) |
| **Release Status v1.0.1** | **RELEASE_AUTHORIZED** | Patch release de higiene de metadata, targets genéricos y documentación post-v1 |

---

## 2. Parámetros del Canal Seguro Pi → Target Worker y Gateway

- **Origen**: `mcp-gateway@MCP-Pi` (`192.168.68.85`, UID 1001, no sudo)
- **Destino (Target actual)**: `u0_a435@192.168.68.72:8022` (Alias: `pc-local` / `termux-local`, target ID: `termux-main`)
- **Autenticación**: Clave pública Ed25519 exclusiva (`mcp_gateway_ed25519`)
- **Host Key Alias**: `termux-main` (identidad fijada en `~/.ssh/known_hosts`, desacoplada de la IP)
- **Host Fingerprint**: `SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`
- **Proyectos Autorizados**:
  - `MCP_Local` -> `/data/data/com.termux/files/home/Projects/test/MCP_Local` (read: true, write: false)
  - `write_smoke` -> `/data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-write-smoke` (read: true, write: configurable)
- **DHCP_RESERVATION**: `RECOMMENDED_FOR_STABILITY` (Recomendación: fijar IP para termux-main en router/Deco cuando la MAC sea provista por Android)
- **Consola de Administración**: `http://127.0.0.1:8080` (accesible exclusivamente mediante túnel SSH `ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85`)
- **Servidor MCP (Streamable HTTP)**: `http://127.0.0.1:8090/mcp` (confinado a loopback, servicio `mcp-gateway-mcp.service` vía `mcp-gateway-adapter`)
- **Servidor MCP (Stdio sobre SSH)**: Invocación vía clave dedicada por cliente a `mcp-gateway@192.168.68.85` ejecutando `mcp-gateway-client-stdio <client_id>` con el adaptador Go oficial (`mcp-gateway-adapter --transport stdio --client-id <id>`)
- **Backups Locales de Escritura**: `~/.local/share/mcp-gateway/backups/...` (almacenados en la Raspberry Pi Gateway, hasta 5 versiones por archivo)
- **Bóveda Fuera de Git**: `C:\Users\esaud\.mcp_migration_backup` (almacenada en la estación de trabajo fuera del repositorio)

---

## 3. Metadatos de Control

- **LAST_VERIFIED**: 2026-09-09 21:15 CST (2026-09-10 03:15 UTC)
- **CURRENT_PHASE**: V1.0.1 POST-V1 HYGIENE PATCH RELEASE
- **ROADMAP**:
  - **Fase 5**: Controlled Write (COMPLETADA)
  - **Fase 6A**: Local AI Clients, Identity & Grants (COMPLETADA)
  - **Three-Way Audit**: Source of Truth Alignment (PASS)
  - **Fase 7A**: Resilience, Audit & Baseline Readiness (COMPLETADA)
  - **Fase 7B**: OS Migration to Debian 13 Trixie (DEFERRED_POST_V1)
  - **v1.0.0 Release**: RELEASED (commit `d52f848`)
  - **v1.0.1 Release**: IN_PROGRESS (fix/v1.0.1-hygiene)
  - **Fase 6B**: ChatGPT & Cloud AI Ingress Gate (Bloqueada hasta túnel autenticado formal)
- **RELEASE_STATE**:
  - RC_TAG: `v1.0.0-rc1` @ `1df371c`
  - STABLE_TAG: `v1.0.0` @ `d52f848`
  - PATCH_TAG: `v1.0.1` (pending merge)
  - ROLLBACK_FAIL_CLOSED: PASS
  - ROLLBACK_FUNCTIONAL_SANDBOX: PASS
  - FORMAL_SOAK: PASS (60 min)
  - TARGET_HOST_KEY_MATCH: PASS
  - TARGET_RETURN: PASS (5/5 operaciones)
  - PHASE5_LIVE_TARGET: PASS (19/19)
  - FULL_PATH: PASS
  - SECURITY_NEGATIVE_SUITE: PASS (7/7)
  - REGRESSIONS: PASS (Python 107/107 local, 107/107 Pi, Go 10/10, Phase 6A 4/4, Doctor HEALTHY)
  - v1.0.0: RELEASED
  - v1.0.1: RELEASE_AUTHORIZED
- **NEXT_ACTION**: MERGE_AND_TAG_V1.0.1


