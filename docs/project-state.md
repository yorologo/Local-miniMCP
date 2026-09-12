# Estado Operacional del Proyecto - MCP Raspberry Pi Gateway

Documento de seguimiento continuo y estado de componentes del sistema.

---

## 1. Matriz de Verificación Operacional

| Componente / Verificación | Estado | Detalle / Evidencia |
|---|---|---|
| **Raspberry identificada** | **PASS** | BCM2835, Model A+ Rev 1.1, ARMv6l (`MCP-Pi`) en `192.168.68.85` |
| **Hostname & Colisión** | **PASS** | Hostname establecido en `MCP-Pi`. Colisión con Pi-hole (`YorPi`) resuelta. |
| **SSH Administrativo** | **PASS** | OpenSSH 8.4p1 activo en puerto 22 (`Yorologo@192.168.68.85`) |
| **Identidad Técnica Pi** | **PASS** | Usuario `mcp-gateway` creado (UID: 102, GID: 105 en Trixie; histórico Bullseye: UID 1001, sin sudo, sin login por password) |
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
| **Gateway Core (Fase 4A)** | **PASS** | Arquitectura multi-target, Python stdlib (cero dependencias externas), UID 102 en Trixie (histórico Bullseye: UID 1001) |
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
| **ChatGPT Gate & Secure MCP Tunnel** | **LOCAL_SIDE_READY / OPENAI_PRODUCT_GATE_PENDING** | Túnel oficial saliente OpenAI (`openai-tunnel-client` ARMv6) con guard systemd `ExecCondition`, cliente `chatgpt-main` registrado con grants de lectura y administración del appliance, 14 herramientas MCP verificadas en vivo, cero puertos expuestos |
| **Appliance Administration Tools** | **PASS** | 5 herramientas seguras de alto nivel (`gateway_status`, `gateway_doctor`, `gateway_backup`, `gateway_maintenance`, `gateway_reboot`) verificadas contra el Core de Políticas sin shell arbitrario |
| **Autonomous Appliance Maintenance** | **PASS** | `mcp-gateway-postboot.service` (doctor en arranque), `mcp-gateway-maintenance.timer` (rotación y chequeo semanal) activos en producción |
| **MCP Reboot Fire Test** | **PASS** | Invocación E2E `gateway_reboot` vía MCP Streamable HTTP -> ciclo de apagado y re-arranque en 89.0s -> Doctor 19/19 HEALTHY -> Target operations 100% restauradas |
| **Target Worker Boot Persistence** | **PASS** | `~/.termux/boot/start_sshd.sh` y fallback en `~/.zshrc` con `termux-wake-lock` configurados y probados en `termux-main` |
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
| **Release Status v1.0.0** | **RELEASED** | Release formal v1.0.0 completado y publicado (commit `d52f848`, tag `v1.0.0`) |
| **Release Status v1.0.1** | **RELEASED** | Patch release de higiene de metadata, targets genéricos y documentación post-v1 (commit `bcd8fe9`, tag `v1.0.1`) |
| **Release Status v1.1.0** | **RELEASE_AUTHORIZED** | Minor feature & hardening release: anti-spoofing trust boundary, appliance management tools, controlled reboot helper, tool catalog v3 (tag `v1.1.0`) |


---

## 2. Parámetros del Canal Seguro Pi → Target Worker y Gateway

- **Origen**: `mcp-gateway@MCP-Pi` (`192.168.68.85`, UID: 102, GID: 105 en Trixie; histórico Bullseye: UID 1001, no sudo)
- **Destino (Target actual)**: `u0_a435@<dynamic_endpoint>:8022` (Alias: `termux-local`, Target ID: `termux-main`)
- **Resolución Dinámica de IP**: Activa y validada en producción (Descubrimiento criptográfico multinivel, fail-closed, single source of truth en SQLite)
- **Autenticación**: Clave pública Ed25519 exclusiva (`mcp_gateway_ed25519`)
- **Host Key Alias**: `termux-main` (identidad fijada en `~/.ssh/known_hosts`, desacoplada de la IP)
- **Host Fingerprint**: `SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`
- **Proyectos Autorizados**:
  - `MCP_Local` -> `/data/data/com.termux/files/home/Projects/test/MCP_Local` (read: true, write: false)
  - `write_smoke` -> `/data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-write-smoke` (read: true, write: configurable)
- **DHCP_RESERVATION**: Opcional / no requerida para continuidad operativa (Resuelta vía descubrimiento criptográfico automático ante rotación de IP)
- **Consola de Administración**: `http://127.0.0.1:8080` (accesible exclusivamente mediante túnel SSH `ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85`)
- **Servidor MCP (Streamable HTTP)**: `http://127.0.0.1:8090/mcp` (confinado a loopback, servicio `mcp-gateway-mcp.service` vía `mcp-gateway-adapter`)
- **Servidor MCP (Stdio sobre SSH)**: Invocación vía clave dedicada por cliente a `mcp-gateway@192.168.68.85` ejecutando `mcp-gateway-client-stdio <client_id>` con el adaptador Go oficial (`mcp-gateway-adapter --transport stdio --client-id <id>`)
- **Backups Locales de Escritura**: `~/.local/share/mcp-gateway/backups/...` (almacenados en la Raspberry Pi Gateway, hasta 5 versiones por archivo)
- **Bóveda Fuera de Git**: `C:\Users\esaud\.mcp_migration_backup` (almacenada en la estación de trabajo fuera del repositorio)

---

## 3. Metadatos de Control

- **LAST_VERIFIED**: 2026-09-10 13:35 CST (2026-09-10 19:35 UTC)
- **CURRENT_PHASE**: POST_V1_OPERATION_AND_MAINTENANCE (Phase 8 CLOSED / PASS; Trixie in Production)
- **CURRENT_MODE**: POST_V1_OPERATION_AND_MAINTENANCE
- **ROADMAP**:
  - **Fase 5**: Controlled Write (COMPLETADA)
  - **Fase 6A**: Local AI Clients, Identity & Grants (COMPLETADA)
  - **Three-Way Audit**: Source of Truth Alignment (PASS)
  - **Fase 7A**: Resilience, Audit & Baseline Readiness (COMPLETADA)
  - **Fase 7B**: OS Migration to Debian 13 Trixie (DEFERRED_POST_V1)
  - **v1.0.0 Release**: RELEASED (commit `d52f848`)
  - **v1.0.1 Release**: RELEASED (commit `bcd8fe9`)
  - **Fase 8**: OS Modernization (Trixie / Debian 13): CLOSED / PASS
    - Base OS Boot & Validation: PASS
    - Rescue Network (USB Tether): PASS
    - RTL8188EUS Wi-Fi (rtl8xxxu): PASS
    - Authoritative SSH Identity Restore: PASS (`AUTHORITATIVE_MCP_PI_IDENTITY`)
    - Bootstrap Temporary SSH Key: RETIRED (`RETIRED_BOOTSTRAP_IDENTITY`)
    - Direct USB Stability (37 MB Transfer): PASS
    - Hub Diagnosis: `HUB_PATH_STRONGLY_IMPLICATED_BY_A_B_TESTING`
    - Regulatory Domain: Configured MX, effective 98 (AP advertises US)
    - v1.0.1 Application Restore: PASS
    - Doctor: 19/19 HEALTHY
    - Functional Smoke: PASS
    - Full Regression: PASS
      - Python Full Suite on Trixie: 107/107 PASS (113.61s)
      - Go MCP Adapter Tests: 10/10 PASS (1.399s)
      - Live Controlled Write (Phase 5): 19/19 PASS
      - Authorization Precedence vs Operational Switch: PASS
      - Local AI Clients & Grants (Phase 6A): 4/4 PASS (78.84s)
      - Canonical Security Negative & Ingress Controls: 8/8 DENIED + 3/3 Ingress PASS (56.94s)
      - MCP Protocol & Target Operations: 8/8 Tools PASS (40.35s)
      - Post-Regression Doctor: 19/19 HEALTHY
      - Service Survival: Admin PID 5297 (0 restarts), MCP PID 5298 (0 restarts)
    - Post-Regression Hygiene Audit: PASS (0 local/deployed app drift, Termux temp DB removed, 0 temp grants, writes_enabled: false, Secret Gate PASS)
    - Reboot Acceptance: PASS
      - Host Reacquisition & Fingerprint Matching (`SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E`): PASS
      - Base OS & ext4 Clean Mount: PASS (0 failed units)
      - Wi-Fi Auto-Recovery (RTL8188EUS / wlan0): PASS (DHCP/DNS/Ping 1.1.1.1 0% loss)
      - Systemd Services Auto-Start: PASS (Admin PID 845, MCP PID 846, loopback bound)
      - SQLite DB Integrity & Security Posture: PASS (integrity ok, user_version 1, writes_enabled false, sudo NO)
      - Target Worker Return (`termux-main`): PASS (4/4 ops ok: status, read, git, task)
      - Post-Reboot Doctor: 19/19 HEALTHY
      - Adapter HTTP Endpoints: 200 OK (/live, /ready, /health, /server/discover)
      - Resource Fit: RAM available 73MB, zram 12MB used, Temp 34.2°C, throttled 0x0, 0 dmesg USB/OOM errors
    - Formal 60-Minute Soak: PASS
      - Continuous observation: 60 minutes (12/12 samples every 5 min)
      - Service survival: Admin PID 845 (0 restarts), MCP PID 846 (0 restarts)
      - Memory stability: MemAvailable 73MB -> 71MB, zram 27.7MB -> 27.2MB (0 OOM, 0 runaway RSS)
      - Thermal & Power: Temp 33.6°C - 34.2°C, Throttled 0x0
      - Network & USB: 0 drops, 0 resets, ping 1.1.1.1 0% loss
      - Target worker (termux-main): T0, T30, T60 E2E probes 100% PASS
      - End-of-soak Doctor: 19/19 HEALTHY
      - End-of-soak DB integrity: ok, writes_enabled: false
    - Production Baseline Promotion: PASS (TRIXIE_PROMOTED_TO_PRODUCTION_BASELINE)
  - **Fase 6B**: ChatGPT & Cloud AI Ingress Gate (Túnel integrado con auth anti-spoofing; credentials pendientes)
  - **v1.1.0 Release**: RELEASED (commit `b2f35d3`)
  - **v1.1.1 Patch Release**: RELEASED (Tunnel Auth Wiring & Trust Boundary Alignment)
    - Upstream `openai/tunnel-client` header resolution rules resolved: dedicated `X-MCP-Gateway-Auth: file:...`
    - Dual-header authentication (`X-MCP-Gateway-Auth` + `Authorization` backward compat)
    - Anti-spoofing protection and safe header coexistence
    - Real hardware acceptance on Raspberry Pi Model A+:
      - Python unit tests: 114/114 PASS (100% test pass rate)
      - Go adapter tests: 11/11 PASS
      - Real hardware auth tests: 7/7 PASS
      - Unified Doctor: 19/19 HEALTHY
      - Controlled appliance reboot: PASS
  - **v1.2.0 Minor Feature Release**: RELEASED
    - Autonomous Dynamic Target Endpoint Resolution & Cryptographic Discovery
    - Paradigm: `TARGET_ID + SSH HOST KEY = IDENTITY`, `IP + PORT = MUTABLE ENDPOINT`
    - Single source of truth in SQLite (`targets.host`), overriding static `~/.ssh/config`
    - Host Key Pinning via `-o HostKeyAlias={target_id}` with `StrictHostKeyChecking=yes`
    - Tiered discovery: Fast Path (direct connect) -> Fast Discovery (`/proc/net/arp`) -> Fallback Discovery (dynamic active LAN scan)
    - Cryptographic validation: Multi-key `ssh-keyscan` verified against `known_hosts`
    - DHCP IP reuse edge case resolution: `ENDPOINT_IDENTITY_MISMATCH` classification (foreign host rejected, discovery finds canonical target on new endpoint)
    - Auth failures remain strictly fail-closed (`AUTH_FAILURE` -> no discovery)
    - Atomic DB update + `activity` audit logging + single automatic retry
    - Zero external tools/daemons (no avahi, no arp-scan, no nmap)
    - Zero schema changes (SQLite Schema v1 preserved)
    - Python Unit Tests: 131/131 PASS (100% test pass rate)
    - Go Adapter Tests: 11/11 PASS
    - Unified Doctor: 19/19 HEALTHY
    - Real Hardware Acceptance on MCP-Pi:
      - Live Stale Endpoint Recovery: PASS (5.47 s)
      - Real Network Interruption Test (81.9s outage): PASS (fast path restoration in 1.17 s, 0 corruptions, 0 storms)
      - Controlled MCP-Pi Reboot Test: PASS (Doctor 19/19, target_status PASS, read_file PASS)
- **RELEASE_STATE**:
  - STABLE_TAG: `v1.2.0`
  - PRODUCTION_OS_BASELINE: `Raspberry Pi OS Lite 32-bit (Debian 13 Trixie / armv6l)`
  - CURRENT_SERVICE_USER: `mcp-gateway` (UID: 102, GID: 105, sudo: NO)
  - BULLSEYE_MICROSD: PRESERVED AS KNOWN_GOOD_PHYSICAL_ROLLBACK UNTIL EXPLICIT DECOMMISSION DECISION
  - TRIXIE_PRODUCTION_STATUS: PROMOTED_TO_PRODUCTION_BASELINE
  - APPLICATION_BASELINE: MCP-Pi Gateway v1.2.0
  - PHASE_8_STATUS: CLOSED / PASS
  - ALL_GATES: PASS
- **NEXT_ACTION**: NORMAL_OPERATION


