# Lista de Verificación y Criterios de Aceptación — Release v1.0.0-rc1

Documento formal de control de calidad, resiliencia y seguridad para la certificación de la versión candidata **MCP-Pi Gateway v1.0.0-rc1**.

---

## Matriz de Criterios de Aceptación (37 Puntos)

| # | Área de Control | Requisito | Estado | Evidencia / Verificación |
|---|---|---|---|---|
| **1** | **Baseline Freeze** | Git limpio en commit `ee23898`, tag `phase-6a-pass` | **PASS** | `git status --short` limpio, `git log -1` verificado |
| **2** | **Inventario Técnico** | Snapshot exhaustivo de hardware, SO, red y servicios | **PASS** | Documentado en `docs/migration/pre-migration-inventory.md` |
| **3** | **Backup Gate** | Backup lógico online e integridad validada | **PASS** | `gateway_backup_*.db` y `export_pre_migration.json` en bóveda |
| **4** | **Bóveda Fuera de Git** | Almacenamiento seguro de secretos fuera del repo | **PASS** | Vault local `~/.mcp_migration_backup/` con permisos 600 |
| **5** | **Integridad de Backup** | SQLite `PRAGMA integrity_check` en copia local | **PASS** | Resultado: `ok`, `user_version = 1`, 9 tablas verificadas |
| **6** | **Rollback Físico** | MicroSD Bullseye preservada sin alteraciones | **PASS** | Tarjeta original protegida como `KNOWN_GOOD_PHYSICAL_ROLLBACK` |
| **7** | **Candidato SO Primario** | Raspberry Pi OS Lite 32-bit (Debian 13 Trixie) | **PASS** | Imagen oficial verificada (URL, fecha 2026-06-18, SHA256) |
| **8** | **Candidato SO Fallback** | Raspberry Pi OS Legacy Lite 32-bit (Bookworm) | **PASS** | Imagen fallback catalogada ante blockers de hardware |
| **9** | **Arquitectura CPU** | Soporte estricto para SoC BCM2835 (ARMv6l) | **PASS** | Tag oficial `pi1-32bit`, CERO binarios de 64-bit |
| **10** | **Wi-Fi Hardware Gate** | Realtek RTL8188EUS (`0bda:8179`) y driver `r8188eu` | **PASS** | Driver estable en kernel Linux, link quality verificado |
| **11** | **Preservación Host Key** | Clave de host SSH Ed25519 inmutable | **PASS** | Clave respaldada; fingerprint `SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E` |
| **12** | **Host Key Pinning** | `StrictHostKeyChecking=yes` en clientes | **PASS** | Archivo `~/.ssh/mcp_known_hosts` con pinning forzado |
| **13** | **Fallo Seguro SSH** | Rechazo fail-closed ante clave adulterada | **PASS** | Código de salida 255 comprobado en prueba negativa |
| **14** | **Identidad de Clientes** | Gemini CLI y Claude Desktop clasificados verídicamente | **PASS** | Clasificados como `NOT_INSTALLED`; cliente real: `ANTIGRAVITY` |
| **15** | **Unificación MCP** | Solo UNA implementación MCP activa (Go SDK) | **PASS** | `stdio_server.py` eliminado; Go SDK v1.7.0 estático oficial |
| **16** | **Go SDK Test Suite** | Cobertura total de pruebas unitarias en Go | **PASS** | 10/10 tests Go aprobados (stdio, dynamic grants, disabled) |
| **17** | **Precedencia de Autorización** | Grants evaluados antes que interruptores operativos | **PASS** | Precedencia verificada; cliente sin grant no recibe fugas de estado |
| **18** | **Controlled Write** | Mutación atómica con doble autorización | **PASS** | `writes_enabled=true` AND `project.write=true`, `expected_sha256` |
| **19** | **Botón de Pánico** | Desactivación inmediata de escrituras | **PASS** | `/settings/disable-writes` bloquea escrituras manteniendo lecturas |
| **20** | **Target Offline Handling** | Comportamiento fail-closed ante target desconectado | **PASS** | Retorna en 168 ms (`SSH_FAILED`), sin bloqueos ni corrupción |
| **21** | **Reboot Recovery** | Auto-arranque de servicios tras reinicio | **PASS** | Servicios systemd con `Restart=on-failure`, IP estática reservada |
| **22** | **Wi-Fi Disruption** | Recuperación ante caída temporal de enlace inalámbrico | **PASS** | Reconexión automática sin reiniciar servicios loopback |
| **23** | **Instalador Idempotente** | Script `install.sh` reproducible y seguro | **PASS** | Verificada doble ejecución consecutiva sin efectos adversos |
| **24** | **Lifecycle CLI** | Comandos unificados `setup` y `update --check` | **PASS** | Manifest y `SHA256SUMS` intactos, modo `--check` verificado |
| **25** | **Doctor de Salud** | Chequeo integral del sistema | **PASS** | `mcp-gateway doctor`: `OVERALL STATUS: HEALTHY` |
| **26** | **Pruebas Python Locales** | Suite unitaria completa en estación de trabajo | **PASS** | 107/107 pruebas aprobadas en 56.4s |
| **27** | **Pruebas Python Remotas** | Suite unitaria completa en Raspberry Pi A+ | **PASS** | 107/107 pruebas aprobadas en MCP-Pi |
| **28** | **Live Client E2E** | Verificación en vivo sobre sesiones SSH Stdio reales | **PASS** | 4/4 bloques aprobados en `scripts/verify_phase_6a.py` |
| **29** | **MCP 2026 Native** | Streamable HTTP con cabecera `Stateless: true` | **PASS** | Endpoints `/server/discover` y `/mcp` con SSE chunked activos |
| **30** | **Protección de Red HTTP** | Filtrado estricto de Host y Origin loopback | **PASS** | Intentos maliciosos de DNS rebinding rechazados con HTTP 403 |
| **31** | **Límites de Recursos** | Uso de memoria acotado para ~176 MiB RAM | **PASS** | Admin RSS ~15 MB, MCP Adapter RSS ~10 MB, RAM libre > 30 MB |
| **32** | **Retención de Logs** | Crecimiento acotado sin dependencias pesadas | **PASS** | Sin Prometheus/Grafana/ELK; journald acotado y rotación rodante |
| **33** | **Puertos Esperados** | Cero listeners inesperados | **PASS** | Confinados: 8080 (Admin), 8090 (MCP), 22 (SSH LAN) |
| **34** | **Protección Pi-hole** | Aislamiento estricto de `192.168.68.54` | **PASS** | Dispositivo intocable, cero comandos ejecutados |
| **35** | **Higiene Git** | Repositorio limpio y sin secretos | **PASS** | Cero claves privadas, cero credenciales, `git status` limpio |
| **36** | **Runbooks Completos** | Documentación de operación y contingencia | **PASS** | Runbooks creados en `docs/runbooks/` y `docs/` |
| **37** | **Versión Candidata** | Liberación de `v1.0.0-rc1` | **PASS** | Checkpoint de control cerrado exitosamente |
