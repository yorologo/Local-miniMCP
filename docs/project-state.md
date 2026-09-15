# Estado Actual — Local-miniMCP / MCP-Pi Gateway

**Última actualización:** 2026-09-13  
**Fase operativa:** `POST_V1_OPERATION_AND_MAINTENANCE`  
**Misión canónica:** [`docs/mission.md`](mission.md)

Este documento describe el **estado actual**. La evidencia detallada histórica permanece en `docs/releases/`, runbooks y Git history.

---

## 1. Objetivo estratégico

MCP-Pi existe para reducir al mínimo la intervención manual del usuario entre ChatGPT/IA y sus dispositivos.

El modelo buscado es:

```text
Usuario
→ define objetivos, límites y decisiones importantes

ChatGPT / IA autorizada
→ inspecciona
→ planifica
→ actúa
→ lee resultados
→ valida
→ continúa cuando es seguro

MCP-Pi
→ autentica
→ autoriza
→ limita
→ delega
→ audita
→ recupera

Targets
→ ejecutan el trabajo real
```

Objetivo estratégico alcanzado:

```text
OPENAI → MCP-PI REMOTE AUTONOMOUS E2E: ACHIEVED
MISSION_V1: ACHIEVED
```

Se demostró exitosamente un ciclo real donde un producto OpenAI en la nube (ChatGPT Plus en espacio personal con Developer Mode y custom MCP app "MCP-Pi" vía Secure MCP Tunnel) usó MCP-Pi para observar el target (`termux-main`), consultar `MCP_Local`, leer el resultado e identificar drift documental de forma completamente autónoma, sin que el usuario actúe como relevo manual de comandos (`HUMAN_COMMAND_RELAY: NOT_REQUIRED`).

Siguiente modo operativo:

```text
POST_V1_OPERATION_AND_MAINTENANCE
```

No inventar V2. No abrir nuevas features.

---

## 2. Baseline de producción

| Campo | Estado actual |
|---|---|
| Software | **MCP-Pi Gateway 1.3.0** |
| Release tag | `v1.2.1` es el último tag inmutable; 1.3.0 se ejecuta desde `develop` por SHA exacto |
| `main` | `v1.2.1` (`0f1ed929757127f7666cfa23b5615f4868372253`) — línea de release inmutable |
| `develop` | **1.3.0 current software/production baseline**, exact-commit deployment |
| Hardware | Raspberry Pi Model A+ Rev 1.1, ARMv6 |
| OS producción | Raspberry Pi OS / Debian 13 Trixie, 32-bit `armv6l` |
| Gateway hostname | `MCP-Pi` |
| Gateway LAN | `192.168.68.55` (reserva DHCP operativa; IP no sustituye identidad SSH) |
| Service user | `mcp-gateway` UID 102 / GID 105, sin sudo general |
| Admin Web | `http://192.168.68.55` (`0.0.0.0:80`, LAN allowlisted) |
| MCP HTTP | `127.0.0.1:8090/mcp` |
| Registry | SQLite, `PRAGMA user_version=1` |
| Writes globales | `false` por defecto |
| Doctor | `19/19 HEALTHY`; debe revalidarse después de cada exact-commit deploy |
| Physical rollback | microSD Bullseye original preservada `KNOWN_GOOD` |

Fingerprint administrativa canónica de MCP-Pi:

```text
SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E
```

Pi-hole independiente:

```text
YorPi / 192.168.68.54
```

**Regla permanente:** Pi-hole está fuera del alcance de MCP-Pi. No modificarlo, reiniciarlo ni usarlo como host del Gateway.

---

## 3. Target real validado

```text
Target ID: termux-main
Platform: Android 16 / Termux
User: u0_a435
Port: 8022
Endpoint: dinámico (192.168.68.84:8022 actualmente)
Project: MCP_Local
Root: /data/data/com.termux/files/home/Projects/test/MCP_Local
Entorno SSH: sshd_config.d/termux-environment.conf (TERMUX_VERSION=0.118.3)
```

Fingerprint canónica:

```text
SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0
```

Invariante:

```text
TARGET_ID + SSH HOST KEY = IDENTITY
IP + PORT                 = MUTABLE ENDPOINT
MAC                       != IDENTITY
IP                        != IDENTITY
```

`v1.2.0` incorpora discovery criptográfico on-demand, recuperación de stale endpoint, manejo seguro de reutilización DHCP, `HostKeyAlias`, `StrictHostKeyChecking=yes`, Registry como fuente única de endpoint y retry único después de identity match.

---

## 4. Estado de la pila local

```text
MCP_PI:                       PRODUCTION_READY
TERMUX_MAIN:                  PRODUCTION_READY / SELF_HEALING
ANDROID_COLD_REBOOT_RECOVERY: PASS
DYNAMIC_TARGET_DISCOVERY:     PRODUCTION_READY
DHCP_IP_CHANGE_RECOVERY:      PASS
NETWORK_INTERRUPTION:         PASS
MCP_PI_REBOOT:                PASS
SECURE_MCP_TUNNEL:            PRODUCTION_READY
DISASTER_RECOVERY:            ACCEPTED_WITHOUT_BARE_METAL_RESTORE
SCHEMA:                       v1
WRITES:                       false
DOCTOR:                       19/19
LOCAL_STACK:                  COMPLETE
```

Evidencia principal de resiliencia y hardening local:

- Python regression: `131/131 PASS`;
- Go adapter: `11/11 PASS`;
- MCP-Pi discovery tests: `17/17 PASS`;
- stale-IP recovery real: `5.47 s`;
- network interruption controlada: `81.9 s`, recuperación automática;
- MCP-Pi controlled reboot: `PASS` (tiempo total SSH ~3m 32s, túnel ~5m 16s determinista);
- DB integrity: `ok`;
- nuevas dependencias externas: `0`;
- nuevos daemons para discovery: `0`.

### 4.1 Android Cold-Reboot Persistence Acceptance

Reboot físico real de Android (`termux-main`) ejecutado y validado operacionalmente:

- **Ejecución física:** reboot real del dispositivo móvil sin apertura manual de Termux ni interacción de usuario en la UI.
- **Auto-start de servicios background:** Termux:Boot arrancó exitosamente `sshd` (puerto 8022), `termux-wake-lock`, watchdog y `crond`.
- **Métricas de recuperación observadas:**
  - Recuperación de conectividad e interfaz SSH (puerto 8022): ~48.8 s.
  - Recuperación y disponibilidad de Target por el Gateway: ~49.6 s.
- **Intervención manual en Gateway:** `NO` (0 comandos manuales en MCP-Pi).
- **Auto-recuperación de servicios y daemons:**
  - `sshd` auto-start: `YES`.
  - `watchdog` auto-start: `YES`.
  - `crond` auto-start: `YES`.
- **Verificación funcional de herramientas del Target:**
  - `target_status`: `PASS`.
  - `git_status`: `PASS`.
  - `read_file`: `PASS`.
- **Precisión técnica:** La IP del dispositivo se mantuvo idéntica (`192.168.68.84`) tras el reinicio; la validación verificó la persistencia y recuperación vía Fast Path con pinning criptográfico confirmado (`SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`) sin constituir una nueva prueba de redescubrimiento DHCP.

### 4.2 Disaster Recovery y Política de Respaldo

Se ejecutó y validó la estrategia de recuperación ante desastres (DR) para el appliance MCP-Pi v1.2.1:

```text
DISASTER_RECOVERY:

BACKUP_CREATION:             PASS
OFF_DEVICE_ENCRYPTED_BACKUP: PASS
AES256_HEADER_ENCRYPTION:    PASS
LOGICAL_RESTORE_ACCEPTANCE:  PASS
SHADOW_RUNTIME_ACCEPTANCE:   PASS
RESTORE_GAPS:                0

DISASTER_RECOVERY_READINESS: ACCEPTED_WITHOUT_BARE_METAL_RESTORE
BARE_METAL_RESTORE_TEST:     NOT_EXECUTED_BY_USER_CHOICE
```

#### Política de Respaldo Actual

1. **Appliance Source Backup:**
   - Respaldo completo y autocontenido generado localmente en el appliance con manifest canónico estructurado (`/home/yorologo/backups/`).
2. **Off-Device DR Archive:**
   - Copia privada off-device almacenada en la estación de trabajo local (Windows), protegida mediante contenedor cifrado 7-Zip con algoritmo AES-256 y cifrado de cabeceras (`-mhe=on`).
   - Copias de trabajo en texto claro eliminadas de la estación de trabajo tras verificar la integridad del contenedor cifrado.
3. **Protección de Credenciales y Secretos:**
   - Contraseña del archivo cifrado custodiada separadamente por el usuario en gestor de contraseñas externo (`PASSWORD_STORED_SEPARATELY: YES`).
   - Cero contraseñas, claves privadas, tokens ni credenciales expuestas en Git, scripts o documentación.
   - Respaldo excluido de sincronización cloud pública.

#### Aceptación de Restauración Lógica No Destructiva

Validación de recuperación integral ejecutada en un entorno de staging aislado (`/tmp`) en MCP-Pi sin modificar producción:

- **Integridad y consistencia de datos:**
  - Snapshot de SQLite consistente verificado con `PRAGMA integrity_check=ok` y `PRAGMA user_version=1`.
  - Tablas y conteos de filas idénticos al estado de producción.
- **Identidades criptográficas preservadas:**
  - Clave de host SSH de MCP-Pi verificada (`SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E`).
  - Clave cliente del Gateway (`SHA256:Vd61kRdCrV+JbNYnPyKPLVEQBi7xsQ24Dbug+epdMEY`).
  - Pinning del host target `termux-main` (`SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0`).
- **Permisos y secretos de runtime:**
  - Ficheros sensibles y sockets con permisos restrictivos (0600) y ownership esperado.
- **Binarios de runtime recuperables:**
  - `openai/tunnel-client` (v0.0.14+3b706ea) y adaptador Go `mcp-gateway-adapter` (v1.2.1) íntegros y ejecutables.
- **Aceptación de Shadow Runtime:**
  - Instancia shadow del Gateway levantada sobre puerto de loopback aislado (`127.0.0.1:18090`).
  - Endpoints de salud validados: `/live` retornó HTTP 200, `/ready` retornó HTTP 200.
- **Invariante productiva:**
  - Cero discrepancias (Restore Gaps: 0).
  - Limpieza completa del staging tras la prueba; producción permaneció 100% intacta y en ejecución continua.
- **Alcance de Bare Metal:**
  - El usuario decidió explícitamente prescindir de almacenamiento secundario físico adicional (`SECOND_OFFLINE_DR_COPY = WAIVED_BY_USER`, `BARE_METAL_CLEAN_RESTORE = NOT_PLANNED`).
  - La preparación ante desastres se declara formalmente aceptada a nivel lógico y shadow runtime (`ACCEPTED_WITHOUT_BARE_METAL_RESTORE`).

---

## 5. Arquitectura vigente

```text
AI / MCP Client
       │
       ▼
MCP Adapter
       │
       ▼
Gateway Core
       │
       ▼
Policy
       │
       ▼
Registry / SSH Transport
       │
       ▼
Target Worker
       │
       ▼
Authorized Project / Task
```

Admin Web y MCP deben continuar usando el mismo Core.

No introducir bypasses como:

```text
Admin → SSH directo
MCP Adapter → SSH directo
```

---

## 6. Modelo de autonomía

El usuario no debe ser el mecanismo de transporte entre IA y dispositivo.

La experiencia objetivo es:

```text
observar
→ decidir
→ actuar
→ verificar
→ continuar
```

El usuario interviene para:

- aprobar decisiones importantes;
- cambiar dirección estratégica;
- proporcionar secretos/credenciales cuando corresponda;
- resolver ambigüedad;
- autorizar riesgos fuera de los grants existentes.

La autonomía sigue siendo acotada por Policy + Grants + herramientas explícitas.

---

## 7. Invariantes de seguridad

- KISS.
- Reuse first.
- Least privilege.
- Deny by default.
- Fail closed.
- `StrictHostKeyChecking=yes`.
- Ningún endpoint IP/MAC equivale a identidad.
- Secrets fuera de Git.
- Writes globales deshabilitados por defecto.
- Sin arbitrary shell como contrato MCP principal.
- No exposición pública directa de puertos domésticos por defecto.
- High-level tools antes que generic exec.
- Un solo Gateway Core para Admin y MCP.

---

## 8. Estado de conectividad OpenAI

La infraestructura local necesaria está preparada.

Arquitectura final deseada:

```text
OpenAI / ChatGPT autorizado
          │
          │ MCP oficial seguro
          ▼
        MCP-Pi
          │
          ▼
   Targets privados
```

Ruta local de validación disponible conceptualmente:

```text
Codex / cliente MCP local
→ MCP stdio sobre SSH
→ MCP-Pi
```

Esta ruta es útil para probar clientes y operación local, pero **no sustituye** la meta de ingreso remoto oficial desde OpenAI hacia el appliance siempre encendido.

Para cloud ingress se debe reutilizar primero una capacidad oficial vigente (por ejemplo Secure MCP Tunnel si la organización/cuenta dispone de entitlement y credenciales), en vez de construir un túnel propietario.

Estado actual:

```text
LOCAL_SIDE:                         READY
OPENAI_PLATFORM_AUTH:               VERIFIED (ChatGPT Plus / Developer Mode)
SECURE_MCP_TUNNEL_ENTITLEMENT:      VERIFIED (openai/tunnel-client ARMv6 active)
OPENAI_REMOTE_MCP_E2E:              PASS
CHATGPT_PLUS_CUSTOM_MCP:            PASS
REMOTE_AUTONOMOUS_TOOL_LOOP:        PASS
HUMAN_COMMAND_RELAY:                NOT_REQUIRED
MISSION_V1:                         ACHIEVED
```

Las capacidades y límites de producto de OpenAI cambian; revalidar documentación oficial al ejecutar este frente y no congelar supuestos de plan en la arquitectura.

### 8.1 Spike de Contención Kernel y Delegación a Antigravity en termux-main

Se auditó empíricamente la viabilidad de delegar objetivos de alto nivel a Antigravity en `termux-main` dentro de una frontera técnica de kernel que impida mutaciones sobre el proyecto original cuando `writes_enabled=false`:

- **Antigravity CLI (v1.2.2)**: Dispone de herramientas mutadoras nativas (`write_to_file`, `replace_file_content`, `run_command`). En pruebas empíricas no interactivas (`--print`), `--mode plan` y `--sandbox` no impidieron la mutación física de archivos ante instrucciones de edición.
- **Landlock LSM**: Invocación oficial de syscall 444 (`landlock_create_ruleset`) probada directamente en C sobre el kernel Android 16 (`6.6.118-android15-8-ge56cf6b09cca-ab15511674-4k`), retornando `ENOSYS` (errno 38; `CONFIG_SECURITY_LANDLOCK=n` en el kernel stock/OEM).
- **Namespaces de usuario / Aislamiento**: `unshare(CLONE_NEWUSER)` retorna `EINVAL` (`CONFIG_USER_NS=n`); `unshare(CLONE_NEWNS)` retorna `EPERM` (sin `CAP_SYS_ADMIN`). Bubblewrap no es viable sin user namespaces o root.
- **PRoot**: Rechazado por contrato operativo como frontera de seguridad válida.
- **Resolución KISS**: `NO_SAFE_CONTAINMENT_AVAILABLE` / `DO_NOT_INTEGRATE_YET`.
- **Invariante de seguridad preservada**: No se implementa `delegate_task` en MCP-Pi para evitar un bypass semántico del control maestro `writes_enabled=false`.
- **Estado del Gate**: `ANTIGRAVITY_DYNAMIC_DELEGATION: BLOCKED_BY_NO_SAFE_CONTAINMENT`. Cerrado formalmente; no reabrir sin soporte real de aislamiento en kernel o CLI con flag `--read-only` técnicamente estricto.

### 8.2 Auditoría Oficial de Superficies Consumidoras de OpenAI Secure MCP Tunnel

Se examinó la arquitectura oficial del Secure MCP Tunnel (`openai/tunnel-client`, `onboarding.md`, `connectors.md`, `architecture.md`) y las superficies del ecosistema OpenAI para determinar qué productos pueden consumir un túnel remoto existente:

#### 1. Distinción canónica de roles: Producer vs Consumer
- **Producer / Runtime Manager**: Conecta un MCP privado hacia el control plane de OpenAI (`tunnel-client run`, `tunnel-client runtimes connect`). El plugin `tunnel-mcp` para Codex CLI opera estrictamente como gestor del ciclo de vida del runtime local (`install_or_select_tunnel_client`, `create_tunnel_runtime`, etc.). **No es un consumidor de túneles remotos.**
- **Consumer**: Producto en la nube de OpenAI que envía llamadas JSON-RPC al túnel a través del endpoint virtual `<OPENAI_MCP_TUNNEL_BASE_URL>/v1/mcp/<tunnel_id>`.

#### 2. Matriz de Superficies Consumidoras

| Consumidor | Soportado por Túnel | Disponible en Cuenta Actual | Requiere Facturación Extra | Custom MCP Tooling Completo | Alcanza MCP-Pi Hoy | Blocker Principal |
|---|---|---|---|---|---|---|
| **ChatGPT Plus** | SÍ | SÍ (Developer Mode) | NO (Suscripción Plus activa) | SÍ (Custom MCP vía Tunnel) | SÍ | NINGUNO — Validado exitosamente E2E (`PASS`) |
| **Codex CLI (Plus)** | COMPATIBLE (Producer) / NO CONSUMIDOR REMOTO | SÍ | NO | SÍ (vía local MCP stdio SSH) | NO vía túnel remoto / SÍ vía stdio local SSH (`CODEX_LOCAL_MCP_E2E`) | `CODEX_CLI_REMOTE_TUNNEL_CONSUMER: NO_SUPPORTED_ATTACH_SURFACE_FOUND` (Codex CLI 0.153.3 no expone una interfaz documentada para engancharse como consumidor a un `tunnel_id` remoto ya corriendo en MCP-Pi; su plugin `tunnel-mcp` gestiona runtimes/producers locales. No se extrapola a futuras o internas superficies Codex) |
| **Codex Cloud / App** | NO IDENTIFICADO | N/A | SÍ (en API) | NO | NO | `CODEX_CLOUD_REMOTE_TUNNEL_CONSUMER: NO_DOCUMENTED_STANDALONE_SURFACE` (No se identificó superficie Cloud autónoma documentada para consumir túneles fuera de ChatGPT o Responses API; no extrapolar a capacidades internas) |
| **Responses API** | SÍ | NO | SÍ (Créditos Platform prepagos) | SÍ | NO | `API_BILLING_REQUIRED` (`HTTP 429 credit_balance_exhausted`) |
| **Agents SDK / AgentKit** | SÍ | NO | SÍ (Requiere API Key con saldo) | SÍ | NO | `API_BILLING_REQUIRED` |

#### 3. Conclusión Operativa KISS
- **CURRENT_ACCOUNT_BEST_REMOTE_PATH**: `CHATGPT_PLUS_DEVELOPER_MODE_VIA_SECURE_MCP_TUNNEL` (Validado y operativo).
- Se confirmó y validó que las cuentas ChatGPT Plus en espacio de trabajo personal disponen de acceso a `Settings → Plugins/Complementos → Create Connection → Tunnel` (Developer Mode), permitiendo registrar el complemento `MCP-Pi` conectado directamente al Secure MCP Tunnel oficial (`mcp-pi`) en producción.
- Tanto la ruta local (`CODEX_LOCAL_MCP_E2E`) como la ruta remota en nube (`CHATGPT_PLUS_CUSTOM_MCP` / `OPENAI_REMOTE_MCP_E2E`) quedan 100% validadas y operativas sin requerir facturación adicional ni gateways públicos.

### 8.3 Validación de Recuperación Real de Producción Post-Reboot

Se auditó, resolvió y validó la recuperación física post-reboot (`sudo reboot`) sobre MCP-Pi con credenciales de producción del Secure MCP Tunnel instaladas:

1. **Defecto Inicial (`BOOT_ORDER_DEFECT` / `SERVICE_DEPENDENCY_DEFECT`)**:
   - En el primer boot frío, el inicializador de `mcp-gateway-adapter` tardó ~1m 55s en enlazar el socket `127.0.0.1:8090`.
   - Como `mcp-gateway-mcp.service` es `Type=simple`, systemd inició `mcp-gateway-tunnel.service` 8 segundos antes de que el puerto 8090 estuviese listo, causando `connect: connection refused` en el hook `OnStart` y enclavando `/readyz` en HTTP 503.
2. **Fix Aplicado (Source of Truth en Repo, Zero Runtime Drift)**:
   - Se actualizó el guard `ExecCondition` (`config/systemd/mcp-gateway-tunnel-check` / `/usr/local/bin/mcp-gateway-tunnel-check`) para esperar activamente a que `http://127.0.0.1:8090/live` retorne HTTP 200 (timeout conservador de 120s, poll cada 1s).
   - Se añadió `TimeoutStartSec=180s` en `config/systemd/mcp-gateway-tunnel.service` para dar margen a systemd.
   - Casos unitarios A (fast ready), B (delayed ready), C (timeout fail-closed `MCP_BACKEND_NOT_READY_TIMEOUT`), y D (credentials missing `OPENAI_PRODUCT_GATE_PENDING`) validados aisladamente con 100% de éxito.
3. **Revalidación Post-Reboot Real**:
   - `REBOOT_TO_SSH`: 3m 32s.
   - `REBOOT_TO_GATEWAY_READY`: 4m 33s.
   - `REBOOT_TO_TUNNEL_READY`: 5m 16s (espera activa hasta readiness de backend).
   - `REBOOT_TO_CONTROL_PLANE_POLLING`: 5m 16s.
   - `MANUAL_TUNNEL_RESTART_REQUIRED`: NO (0 intervenciones).
   - `BOOT_RACE_DETECTED_AFTER_FIX`: NO.
   - `CONTROLLED_REBOOT_RECOVERY`: **PASS**.

### 8.4 Aceptación Final: ChatGPT Plus Remote Autonomous E2E (Mission V1 Achieved)

```text
OPENAI_REMOTE_MCP_E2E:       PASS
CHATGPT_PLUS_CUSTOM_MCP:     PASS
REMOTE_AUTONOMOUS_TOOL_LOOP: PASS
HUMAN_COMMAND_RELAY:         NOT_REQUIRED
MISSION_V1:                  ACHIEVED
```

Evidencia resumida:

- ChatGPT Plus personal workspace;
- Developer Mode;
- custom MCP app MCP-Pi;
- Secure MCP Tunnel;
- autonomous read-only evaluation;
- ChatGPT eligió autónomamente herramientas;
- 9 tools utilizadas;
- target termux-main;
- proyecto MCP_Local;
- documentación drift detectada autónomamente;
- ninguna intervención humana como command relay;
- writes_enabled=false.

---

## 9. Acceptance test estratégico completado

El ciclo estratégico de autonomía remota fue demostrado y aceptado formalmente:

```text
Desde un producto OpenAI autorizado (ChatGPT Plus vía Secure MCP Tunnel)
→ sin copiar comandos manualmente (HUMAN_COMMAND_RELAY: NOT_REQUIRED)
→ conectar de forma segura a MCP-Pi (127.0.0.1:8091 / mcp-gateway-adapter)
→ consultar estado de termux-main (target_status PASS)
→ inspeccionar MCP_Local (git_status + read_file PASS)
→ ejecutar tareas autorizadas (health, list_targets, target_status, git_status, read_file)
→ obtener el resultado directamente (JSON-RPC sobre Streamable HTTP)
→ tomar y ejecutar el siguiente paso seguro (autonomía completa)
→ verificar el resultado (análisis y drift detectado)
```

Invariantes operativas preservadas:

```text
POLICY:                 ENFORCED
GRANTS:                 ENFORCED
AUDIT:                  ENABLED
ARBITRARY_SHELL:        NOT REQUIRED / FORBIDDEN
HUMAN_COMMAND_RELAY:    NOT REQUIRED
MISSION_V1:             ACHIEVED
```

---

## 10. Qué NO debemos hacer ahora

No añadir features locales por inercia.

No crear otro soak sin una hipótesis concreta.

No crear otro discovery mechanism.

No crear una API/túnel propietario si una opción oficial satisface la necesidad.

No convertir MCP-Pi en Desktop Commander genérico ni en una shell sin límites.

No hacer que Windows/Desktop Commander sea una dependencia de producción.

No tocar Pi-hole.

No mover ni reescribir tags históricos.

---

## 11. Releases relevantes

```text
v1.0.1  baseline inicial estabilizado
v1.1.1  tunnel auth / anti-spoofing hardening
v1.2.0  dynamic target endpoint resolution & cryptographic discovery
v1.2.1  Secure MCP Tunnel deterministic readiness & autorecovery hardening
1.3.0   filesystem confinement, trusted Target shell controls, audit hardening, Target facts, MCP annotations, reproducible CI/deploy/provenance
```

Software baseline actual:

```text
1.3.0 (develop, exact commit)
latest immutable tag: v1.2.1
```

La evidencia detallada vive en:

- `docs/releases/`;
- `docs/runbooks/`;
- `docs/architecture.md`;
- `AGENTS.md`;
- Git history.

---

## 12. Próxima acción

```text
POST_V1_OPERATION_AND_MAINTENANCE
```

Mantener operación normal y mantenimiento de producción 1.3.0 sin abrir nuevos frentes hasta que exista un trigger real. No inventar V2. No abrir nuevas features. Mantener monitoreo pasivo, retención de backup cifrado off-device y preservación estricta de las invariantes de seguridad fail-closed.
