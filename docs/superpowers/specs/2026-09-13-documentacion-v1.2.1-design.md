# Diseño de consolidación documental para MCP-Pi Gateway v1.2.1

| Campo | Valor |
|---|---|
| Estado | APROBADO PARA PLANIFICACIÓN |
| Fecha | 2026-09-13 |
| Baseline documental | MCP-Pi Gateway v1.2.1 |
| Fase | POST_V1_OPERATION_AND_MAINTENANCE |
| Alcance | Documentación, referencias cruzadas y validación documental |

## 1. Objetivo

Consolidar toda la documentación de MCP-Pi Gateway para que describa sin
ambigüedad el sistema vigente, preserve la evidencia histórica y permita a una
persona instalar, configurar, validar, operar y recuperar una instalación nueva
de v1.2.1 sobre Debian 13 Trixie.

La documentación resultante debe:

- distinguir estado actual, arquitectura, procedimientos y evidencia histórica;
- eliminar contradicciones de versión, plataforma, catálogo y endpoint;
- proporcionar un manual de instalación limpio, seguro y reproducible;
- explicar tecnologías, requisitos mínimos y decisiones de diseño;
- representar arquitectura, secuencias, estados y datos con Mermaid;
- marcar explícitamente todo componente o procedimiento opcional;
- mantener KISS, least privilege, deny-by-default y fail-closed;
- poder validarse con herramientas ya presentes en el repositorio.

## 2. Restricciones

- Los tags y documentos de release históricos no se reescriben como si
  pertenecieran a v1.2.1.
- Inventarios, aceptación v1 y migración conservan sus observaciones históricas.
- Pi-hole `YorPi` permanece fuera de alcance.
- Ningún procedimiento debe recomendar exposición pública directa.
- No se documenta `StrictHostKeyChecking=no` ni `accept-new` como solución
  operacional permanente.
- No se incluyen claves privadas, tokens, contraseñas ni contenido de
  `gateway.db`.
- Las IP se tratan como endpoints observados y mutables, nunca como identidad.
- No se añade un generador de sitio, framework documental ni dependencia de
  runtime.
- Los cambios visuales ya presentes en el worktree se preservan y no se mezclan
  con el checkpoint de esta especificación.

## 3. Baseline canónico

La documentación vigente se alinea con estos contratos:

| Contrato | Valor |
|---|---|
| Gateway | 1.2.1 |
| Release estable | `v1.2.1` |
| Core API | 1 |
| Bridge API | 1 |
| Tool Catalog | 3 |
| Herramientas de alto nivel | 14 |
| Registry Schema | 1 |
| MCP | 2026-07-28 |
| MCP legacy | 2025-11-25 |
| Go SDK | 1.7.0 |
| Python mínimo | 3.9 |
| Producción | Raspberry Pi OS / Debian 13 Trixie, armv6l |
| Rollback físico | microSD Debian 11 Bullseye preservada |

La versión observada de Python, el UID/GID asignado, las IP y otros datos de
runtime se etiquetan como observaciones, no como requisitos universales.

## 4. Modelo de autoridad documental

| Ámbito | Fuente de verdad |
|---|---|
| Presentación, inicio y navegación | `README.md` |
| Arquitectura e invariantes | `docs/architecture.md` |
| Misión | `docs/mission.md` |
| Estado y siguiente acción | `docs/project-state.md` |
| Instalación limpia | `docs/installation.md` |
| Tecnologías y versiones | `docs/technologies.md` |
| Procedimientos operativos | `docs/runbooks/` |
| Contratos ejecutables | `compatibility.json` y código |
| Conducta de agentes | `AGENTS.md` |
| Evidencia histórica | `docs/releases/`, `docs/inventory/`, `docs/migration/`, `docs/v1-acceptance.md` |

Cuando dos fuentes discrepen, se aplicará el ámbito de autoridad anterior. Una
observación real del runtime prevalece sobre un endpoint escrito, pero no sobre
la identidad de una release o un fingerprint fijado.

## 5. Arquitectura documental

### 5.1 README

`README.md` se reducirá a una portada operativa mantenible:

1. propósito;
2. baseline actual;
3. arquitectura resumida;
4. garantías de seguridad;
5. inicio rápido;
6. tecnologías principales;
7. estado actual;
8. mapa documental;
9. desarrollo y validación;
10. releases y licencia.

No duplicará procedimientos completos, cronologías ni evidencia de aceptación.

### 5.2 Manual de instalación

`docs/installation.md` será el recorrido completo para una instalación nueva.
Cada etapa seguirá este contrato:

```text
OBJECTIVE
REQUIREMENTS
COMMANDS
EXPECTED EVIDENCE
STOP CONDITIONS
ROLLBACK
```

Contenido:

1. alcance y resultado esperado;
2. topología mínima;
3. hardware, software, red y estación administrativa;
4. preparación de Raspberry Pi OS Lite 32-bit / Debian 13 Trixie;
5. cuenta administrativa `yorologo`;
6. red privada y SSH con captura de fingerprint;
7. obtención y verificación de la release v1.2.1;
8. usuario de servicio `mcp-gateway` y layout;
9. instalación idempotente;
10. Registry SQLite y permisos;
11. Admin Web y adaptador MCP en loopback;
12. configuración del primer Target, Project, Client y Grant;
13. validación positiva y negativa;
14. reboot acceptance;
15. primer backup y operación inicial;
16. troubleshooting;
17. checklist de aceptación.

### 5.3 Opcionales

Los siguientes apartados se marcarán `OPCIONAL` y no bloquearán una instalación
local mínima salvo que el usuario los elija:

- preparación de Android/Termux como Target;
- compilación del adaptador con Go;
- recompilación de estilos con Node.js/Tailwind;
- OpenAI Secure MCP Tunnel;
- clientes MCP adicionales;
- restauración de identidad histórica;
- restauración de Registry desde Recovery Vault;
- Android USB tethering de rescate;
- rollback físico Bullseye;
- desarrollo y empaquetado de releases.

Cada opcional declarará prerrequisitos, riesgo, efecto y gate independiente.

### 5.4 Tecnologías

`docs/technologies.md` describirá para cada tecnología:

- versión mínima o fijada;
- uso concreto;
- capa donde se ejecuta;
- si es runtime, build-time u opcional;
- razón de elección;
- impacto esperado en ARMv6;
- alternativas rechazadas cuando la decisión sea relevante.

La matriz incluirá Python, Flask/Jinja2, SQLite, OpenSSH, systemd, Go, MCP Go
SDK, Tailwind CSS, HTMX, POSIX shell, Git y Secure MCP Tunnel.

### 5.5 Documentos especializados

Los documentos de Admin, clientes, grants, controlled writes, compatibilidad,
lifecycle, adaptador MCP y runbooks conservarán sólo el detalle de su ámbito.
Todo resumen repetido se sustituirá por un enlace a la fuente canónica.

### 5.6 Historia

Releases, inventarios, migraciones y aceptación histórica recibirán, cuando sea
necesario, una cabecera breve con:

- tipo de documento histórico;
- baseline al que aplica;
- advertencia de no usar endpoints como estado actual;
- enlace al estado vigente.

No se alterarán resultados, checksums, fechas ni decisiones históricas.

## 6. Diagramas Mermaid

La documentación canónica contendrá:

| Diagrama | Sintaxis | Propósito |
|---|---|---|
| Contexto del sistema | `flowchart` | Usuario, cliente, Gateway, Target y Project |
| Fronteras y despliegue | `flowchart` | Hosts, procesos, puertos y protocolos |
| Componentes | `classDiagram` | Core, Policy, Registry, Tools y Transport |
| Registry schema v1 | `erDiagram` | Target, Project, Client, Grant, Activity, Settings y AdminUser |
| Autorización MCP | `sequenceDiagram` | Auth, tools/list, policy y tools/call |
| Ejecución remota | `sequenceDiagram` | Adapter, Bridge, Core, SSH y Target |
| Recuperación DHCP | `sequenceDiagram` | Fallo de endpoint, discovery, fingerprint y retry |
| Acceso Admin | `sequenceDiagram` | Navegador, túnel SSH y loopback |
| Kill switches | `stateDiagram-v2` | Gateway y controlled writes |
| Instalación | `stateDiagram-v2` | Preflight, instalación, gates y veredicto |
| Update/rollback | `flowchart` | Backup, candidato, doctor, promoción o rollback |
| Recuperación física | `flowchart` | STOP, shutdown, cambio de microSD y verificación |

Cada diagrama tendrá texto alternativo equivalente en el párrafo que lo precede
o sigue, para que el contenido siga siendo comprensible sin render Mermaid.

## 7. Correcciones transversales

Se corregirán sistemáticamente:

- `v1.0.1` presentado como release actual;
- Bullseye presentado como producción vigente;
- IPs antiguas descritas como requisitos;
- UID 1001 presentado como UID actual obligatorio;
- catálogo v2 o 9 herramientas presentado como vigente;
- `apply_patch` descrito como diferido cuando ya forma parte del catálogo v3;
- nombres nuevos basados en `pc-local`;
- ejemplos con bypass de host-key checking;
- enlaces `file://`;
- comandos que contradigan el layout real `/home/mcp-gateway`;
- mezcla de cuenta `Yorologo` con el usuario canónico `yorologo`;
- estados de Phase 6B/8 que omitan su contexto temporal;
- referencias sin enlace a su fuente de evidencia.

## 8. Estrategia de implementación

La implementación se realizará en capas pequeñas:

1. añadir validaciones documentales que fallen con las inconsistencias actuales;
2. consolidar README y mapa de autoridad;
3. crear instalación y tecnologías;
4. actualizar arquitectura y diagramas;
5. alinear AGENTS y estado dinámico;
6. corregir documentos especializados;
7. corregir runbooks;
8. etiquetar historia sin reescribirla;
9. validar enlaces, fences, Mermaid, contratos y secretos;
10. ejecutar las pruebas del software y revisar el diff histórico.

No se editará runtime, Registry, identidades, red ni dispositivos.

## 9. Validación

La comprobación documental usará Python estándar y herramientas existentes. Debe
detectar al menos:

- enlaces Markdown internos inexistentes;
- bloques de código sin cierre;
- enlaces locales `file://`;
- `StrictHostKeyChecking=no` fuera de evidencia histórica explícita;
- baseline vigente diferente de `compatibility.json`;
- README o documentos canónicos que llamen actual a v1.0.1;
- catálogo actual con un conteo distinto de 14;
- documentos operativos que conviertan una IP en identidad;
- referencias canónicas rotas.

Además se ejecutarán:

- suite Python completa;
- pruebas Go con Registry de prueba aislada;
- build Tailwind si se conservan cambios frontend pendientes;
- `git diff --check`;
- Secret Gate sobre contenido real;
- revisión independiente de documentación y comandos.

Los bloques Mermaid se revisarán por sintaxis y consistencia. Si no existe un CLI
Mermaid ya instalado, no se añadirá una dependencia sólo para renderizarlos; la
limitación se informará como tal.

## 10. Gates de aceptación

El trabajo obtiene `PASS` sólo si:

1. el baseline actual coincide en README, AGENTS, arquitectura, instalación,
   tecnologías, estado y `compatibility.json`;
2. el manual permite recorrer una instalación limpia sin depender de secretos o
   estado histórico;
3. los opcionales están identificados explícitamente;
4. no existen instrucciones operativas que relajen host-key checking;
5. todos los enlaces internos son válidos;
6. los diagramas representan componentes y flujos existentes;
7. los documentos históricos siguen siendo distinguibles e inmutables;
8. las pruebas documentales y de software aplicables pasan;
9. el Secret Gate devuelve cero secretos;
10. el diff no mezcla mutaciones de runtime ni reescribe evidencia histórica.

Si falta evidencia de uno o más gates, el resultado será `PARTIAL`. Una
contradicción de seguridad, identidad, schema, release o rollback produce
`STOP` hasta resolverla.

## 11. Decisiones explícitas

- Se elige documentación por capas frente a un README monolítico.
- La instalación limpia es el camino principal.
- Restore, migración, desarrollo y cloud ingress son opcionales.
- Markdown y Mermaid son suficientes; no se añade plataforma documental.
- La precisión y la trazabilidad prevalecen sobre conservar texto duplicado.
- La historia se contextualiza, no se moderniza retroactivamente.
