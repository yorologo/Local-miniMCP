# Estado Actual — Local-miniMCP / MCP-Pi Gateway

**Última actualización:** 2026-09-12  
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

El siguiente objetivo estratégico es:

```text
OPENAI → MCP-PI REMOTE AUTONOMOUS E2E
```

No basta con demostrar conectividad. Debemos demostrar un ciclo real donde un producto OpenAI pueda usar MCP-Pi para observar un target, ejecutar una tarea autorizada, leer el resultado y continuar sin que el usuario copie comandos manualmente.

---

## 2. Baseline de producción

| Campo | Estado actual |
|---|---|
| Software | **MCP-Pi Gateway v1.2.0** |
| Release commit | `df5fa43fe674faaf14b6e557f79b256452c75b22` |
| `main` / `develop` en release | `df5fa43fe674faaf14b6e557f79b256452c75b22` |
| Hardware | Raspberry Pi Model A+ Rev 1.1, ARMv6 |
| OS producción | Raspberry Pi OS / Debian 13 Trixie, 32-bit `armv6l` |
| Gateway hostname | `MCP-Pi` |
| Gateway LAN | `192.168.68.55` (reserva DHCP operativa; IP no sustituye identidad SSH) |
| Service user | `mcp-gateway` UID 102 / GID 105, sin sudo general |
| Admin Web | `127.0.0.1:8080` |
| MCP HTTP | `127.0.0.1:8090/mcp` |
| Registry | SQLite, `PRAGMA user_version=1` |
| Writes globales | `false` por defecto |
| Doctor | `19/19 HEALTHY` en aceptación v1.2.0 |
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
DYNAMIC_TARGET_DISCOVERY:     PRODUCTION_READY
DHCP_IP_CHANGE_RECOVERY:      PASS
NETWORK_INTERRUPTION:         PASS
MCP_PI_REBOOT:                PASS
SCHEMA:                       v1
WRITES:                       false
DOCTOR:                       19/19
LOCAL_STACK:                  COMPLETE
```

Evidencia principal de `v1.2.0`:

- Python regression: `131/131 PASS`;
- Go adapter: `11/11 PASS`;
- MCP-Pi discovery tests: `17/17 PASS`;
- stale-IP recovery real: `5.47 s`;
- network interruption controlada: `81.9 s`, recuperación automática;
- MCP-Pi controlled reboot: `PASS`;
- DB integrity: `ok`;
- nuevas dependencias externas: `0`;
- nuevos daemons para discovery: `0`.

El reboot Android completo permanece como prueba operacional diferida; no bloquea el baseline local actual.

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
OPENAI_PLATFORM_AUTH:               AUTH_REQUIRED / TO_VERIFY
SECURE_MCP_TUNNEL_ENTITLEMENT:      TO_VERIFY WITH OFFICIAL AUTH
OPENAI_REMOTE_MCP_E2E:              NOT_YET_PROVEN
CHATGPT_AUTONOMOUS_E2E:             NOT_YET_PROVEN
```

Las capacidades y límites de producto de OpenAI cambian; revalidar documentación oficial al ejecutar este frente y no congelar supuestos de plan en la arquitectura.

---

## 9. Próximo acceptance test estratégico

El objetivo se considera avanzado de forma material cuando podamos demostrar:

```text
Desde un producto OpenAI autorizado
→ sin copiar comandos manualmente
→ conectar de forma segura a MCP-Pi
→ consultar estado de termux-main
→ inspeccionar MCP_Local
→ ejecutar una tarea autorizada
→ obtener el resultado directamente
→ tomar y ejecutar el siguiente paso seguro
→ verificar el resultado
```

Debe mantenerse:

```text
POLICY:                 ENFORCED
GRANTS:                 ENFORCED
AUDIT:                  ENABLED
ARBITRARY_SHELL:        NOT REQUIRED
HUMAN_COMMAND_RELAY:    NOT REQUIRED
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
```

Release estable actual:

```text
v1.2.0
commit df5fa43fe674faaf14b6e557f79b256452c75b22
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
Investigar y validar la ruta oficial mínima para:
OpenAI → MCP-Pi → target
sin intervención manual del usuario y sin depender de infraestructura propietaria de terceros.
```

Aplicar KISS y reuse-first: primero capacidades oficiales existentes; construir únicamente lo específico de MCP-Pi.
