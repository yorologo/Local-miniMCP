# Matriz de Aceptación y Estado de Migración Real (Phase 7A / 7B)

Documento formal de control de calidad, resiliencia y separación de evidencia entre la línea base Bullseye y la migración física a Debian 13 Trixie.

---

## 1. Estado General de la Fase 7

- **Fase 7A (Preparación, Congelamiento, Inventario y Runbooks)**: **PASS**
- **Fase 7B (Migración Física y Aceptación en Hardware Real)**: **PENDING_PHYSICAL_MIGRATION / BLOCKED_PHYSICAL_MEDIA**
- **Versión Candidata `v1.0.0-rc1`**: **PREMATURE** (Requiere ejecución física en nueva microSD antes del tag)
- **Tag Git Vigente de Preparación**: `phase-7-migration-ready` (HEAD)

---

## 2. Matriz de Control y Evidencia

| # | Área de Control | Requisito | Estado | Evidencia / Tipo de Verificación |
|---|---|---|---|---|
| **1** | **Baseline Freeze** | Git limpio en commit `ee23898`, tag `phase-6a-pass` | **PASS** | `BULLSEYE_BASELINE`: `git status --short` limpio, log registrado |
| **2** | **Inventario Técnico** | Snapshot exhaustivo de hardware, SO, red y servicios | **PASS** | `BULLSEYE_BASELINE`: Registrado en `docs/migration/pre-migration-inventory.md` |
| **3** | **Backup Gate** | Backup lógico online e integridad validada | **PASS** | `BULLSEYE_BASELINE`: `gateway_backup_*.db` y `export_pre_migration.json` |
| **4** | **Bóveda Fuera de Git** | Almacenamiento seguro de secretos fuera del repo | **PASS** | `BULLSEYE_BASELINE`: Vault local `~/.mcp_migration_backup/` con permisos 600 |
| **5** | **Integridad de Backup** | SQLite `PRAGMA integrity_check` en copia local | **PASS** | `BULLSEYE_BASELINE`: Resultado `ok`, `user_version = 1`, 9 tablas verificadas |
| **6** | **Rollback Físico** | MicroSD Bullseye preservada sin alteraciones | **PASS** | `BULLSEYE_BASELINE`: Tarjeta original protegida como `KNOWN_GOOD_PHYSICAL_ROLLBACK` |
| **7** | **Candidato SO Primario** | Raspberry Pi OS Lite 32-bit (Debian 13 Trixie) | **PASS** | Imagen oficial verificada (URL, fecha 2026-06-18, SHA256 validado) |
| **8** | **Candidato SO Fallback** | Raspberry Pi OS Legacy Lite 32-bit (Bookworm) | **PASS** | Imagen fallback catalogada ante blockers de hardware |
| **9** | **Arquitectura CPU** | Soporte estricto para SoC BCM2835 (ARMv6l) | **PASS** | Tag oficial `pi1-32bit`, CERO binarios de 64-bit |
| **10** | **Trixie Boot & Hardware**| Primer arranque de SO limpio en nueva tarjeta | **PENDING_PHYSICAL_MIGRATION** | Requiere segunda microSD física insertada en Raspberry Pi |
| **11** | **Kernel Real Trixie** | Registro de kernel real tras boot | **PENDING_PHYSICAL_MIGRATION** | Requiere captura en vivo de `uname -a` sobre Trixie |
| **12** | **Wi-Fi Hardware Trixie** | Detección de RTL8188EUS (`0bda:8179`) y driver real | **PENDING_PHYSICAL_MIGRATION** | Requiere captura en vivo de `lsusb`, `lsmod` y driver real |
| **13** | **Wi-Fi Stability Trixie**| Estabilidad moderada de enlace inalámbrico | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba de 20 conexiones SSH y ping sobre Trixie |
| **14** | **Bootstrap SSH** | Acceso inicial sin `StrictHostKeyChecking=no` | **PASS** | Procedimiento con `~/.ssh/mcp_bootstrap_known_hosts` en `docs/os-migration.md` |
| **15** | **Preservación Host Key** | Restaurar clave host Ed25519 inmutable | **PENDING_PHYSICAL_MIGRATION** | Requiere restauración en `/etc/ssh/` y verificación de `SHA256:wovttru...` |
| **16** | **Host Key Pinning** | Conexión con `StrictHostKeyChecking=yes` | **PASS** | `BULLSEYE_BASELINE`: Archivo permanente `~/.ssh/mcp_known_hosts` verificado |
| **17** | **Clean Install Trixie** | Despliegue e instalación con `./install.sh` | **PENDING_PHYSICAL_MIGRATION** | Requiere ejecución real de `install.sh` en Trixie |
| **18** | **Idempotencia Install** | Segunda ejecución consecutiva de `install.sh` | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba de doble instalación en Trixie |
| **19** | **Restore Estado Trixie** | Restaurar `gateway.db` y credenciales de servicio | **PENDING_PHYSICAL_MIGRATION** | Requiere restauración selectiva de base de datos y claves en Trixie |
| **20** | **Doctor on Trixie** | Diagnóstico integral en nuevo sistema operativo | **PENDING_PHYSICAL_MIGRATION** | Requiere ejecución real de `mcp-gateway doctor` en Trixie |
| **21** | **Target Worker Connectivity** | Comunicación Pi -> `termux-main` | **PENDING_PHYSICAL_MIGRATION** | Requiere verificación de herramientas remotas desde Trixie |
| **22** | **Regresión Python Trixie** | 107 pruebas unitarias remotas sobre nuevo Python | **PENDING_PHYSICAL_MIGRATION** | Requiere ejecución sobre Python 3.11+ en Trixie |
| **23** | **Regresión Go Trixie** | Ejecución del adaptador estático ARMv6 | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba en vivo del binario `mcp-gateway-adapter` en Trixie |
| **24** | **Controlled Write Trixie** | E2E de mutaciones atómicas en nuevo entorno | **PENDING_PHYSICAL_MIGRATION** | Requiere verificación E2E de escritura controlada desde Trixie |
| **25** | **Client Grants Trixie** | Suite E2E de clientes (`scripts/verify_phase_6a.py`) | **PENDING_PHYSICAL_MIGRATION** | Requiere ejecución de 4/4 bloques contra Trixie |
| **26** | **Reboot Recovery Trixie**| Auto-recuperación de servicios tras reboot real | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba real de `sudo reboot` en Trixie |
| **27** | **Service Recovery Trixie**| Recuperación ante crash de procesos (`Restart=on-failure`) | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba controlada de fallo de servicios en Trixie |
| **28** | **Network Recovery Trixie**| Reconexión tras interrupción de señal Wi-Fi | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba de interrupción controlada en Trixie |
| **29** | **Backup/Restore Trixie** | Backup, modificación controlada y restore en sandbox | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba de ciclo completo de backup en Trixie |
| **30** | **Security Regression** | Vectores negativos bloqueados fail-closed | **PENDING_PHYSICAL_MIGRATION** | Requiere prueba de seguridad perimetral y path traversal en Trixie |
| **31** | **Medición de Recursos** | RAM disponible, RSS Admin, RSS MCP, Swap en Trixie | **PENDING_PHYSICAL_MIGRATION** | Requiere captura real con `free -m` y `ps` sobre Trixie |
| **32** | **Soak Test en Trixie** | Prueba de carga acotada de 30-60 min en nuevo SO | **PENDING_PHYSICAL_MIGRATION** | Requiere monitoreo continuo de memoria y procesos en Trixie |
| **33** | **Listeners en Trixie** | Puertos 8080, 8090 y 22 exclusivamente | **PENDING_PHYSICAL_MIGRATION** | Requiere verificación con `ss -lntup` en Trixie |
| **34** | **Physical Rollback Test** | Apagar Trixie, reinsertar Bullseye y medir RTO real | **PENDING_PHYSICAL_MIGRATION** | Requiere swap físico de vuelta y validación en vivo |
| **35** | **Protección Pi-hole** | Aislamiento estricto de `192.168.68.54` | **PASS** | Intocable en todas las fases |
| **36** | **Higiene Git & Runbooks** | Runbooks creados y cero secretos en Git | **PASS** | 7 runbooks/guías creados, secretos resguardados fuera de Git |
| **37** | **Versión Candidata** | Tag `v1.0.0-rc1` | **PREMATURE** | Pospuesta hasta completar la migración física (Fase 7B) |
