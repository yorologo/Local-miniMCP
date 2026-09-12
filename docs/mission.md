# Misión Canónica — Local-miniMCP / MCP-Pi Gateway

**Estado:** CANÓNICO  
**Fecha:** 2026-09-12  
**Baseline al definir esta misión:** MCP-Pi Gateway `v1.2.0`

---

## 1. Por qué existe MCP-Pi

MCP-Pi nace de una necesidad concreta: eliminar al usuario como intermediario de ejecución cotidiana entre una IA y sus dispositivos.

El flujo manual que queremos superar es:

```text
Usuario define objetivo
→ ChatGPT analiza y genera comandos
→ usuario copia comandos
→ usuario ejecuta
→ usuario revisa resultados
→ usuario devuelve resultados al chat
→ ChatGPT continúa
```

Herramientas como Desktop Commander demostraron que una experiencia mejor es posible: una IA puede observar un dispositivo, ejecutar acciones, leer resultados y continuar trabajando sin que el usuario tenga que trasladar manualmente cada comando y cada respuesta.

Desktop Commander es una **inspiración funcional**, no una dependencia arquitectónica de MCP-Pi. El proyecto busca ofrecer una capacidad equivalente de interacción autónoma controlada mediante infraestructura propia, local, privada, auditable y bajo control del usuario.

---

## 2. Misión

> **MCP-Pi es un gateway MCP privado, permanente y autohospedado que permite a ChatGPT y otros clientes de IA autorizados interactuar de forma segura con dispositivos, proyectos y herramientas dentro de una red privada, reduciendo al mínimo la intervención humana durante la ejecución cotidiana.**
>
> **El usuario conserva el control sobre objetivos, límites, permisos y decisiones importantes; MCP-Pi proporciona identidad, acceso, políticas, auditoría, resiliencia, descubrimiento y ejecución controlada sobre los targets autorizados.**

El objetivo NO es simplemente disponer de un servidor MCP ni proporcionar una shell remota.

El objetivo es permitir un modelo de colaboración como:

```text
USUARIO
│
│ define objetivos de alto nivel
│ establece límites y permisos
│ supervisa ocasionalmente
│ decide cuando existe riesgo, ambigüedad o cambio estratégico
▼
CHATGPT / IA AUTORIZADA
│
│ inspecciona
│ planifica
│ ejecuta herramientas autorizadas
│ lee resultados
│ valida
│ corrige
│ continúa automáticamente cuando es seguro
▼
MCP-PI
│
│ autentica
│ autoriza
│ limita
│ enruta
│ audita
│ descubre targets
│ recupera conectividad
├──────────────┬──────────────┬──────────────┐
▼              ▼              ▼              ▼
Android       Windows        Linux          otros targets
Termux        / Codex CLI    / tools        futuros
```

---

## 3. Papel del usuario

El usuario debe dejar de ser el operador que ejecuta cada instrucción y pasar a ser principalmente:

- **definidor de objetivos**;
- **propietario de políticas y límites**;
- **supervisor**;
- **aprobador de decisiones importantes o riesgosas**;
- **responsable de cambiar la dirección estratégica cuando sea necesario**.

MCP-Pi debe reducir al mínimo solicitudes del tipo:

> “copia este comando, ejecútalo y pégame la salida”.

Ese patrón puede utilizarse excepcionalmente para bootstrap, recuperación o situaciones donde el producto de IA no disponga todavía del canal necesario, pero no representa la experiencia final buscada.

---

## 4. Papel de ChatGPT / cliente de IA

Un cliente de IA autorizado debe poder, dentro de sus grants:

1. observar estado;
2. inspeccionar proyectos;
3. ejecutar tareas permitidas;
4. obtener los resultados directamente;
5. razonar sobre ellos;
6. tomar el siguiente paso cuando sea seguro;
7. detenerse y solicitar intervención humana ante decisiones importantes, riesgo elevado, credenciales ausentes, ambigüedad o límites de política.

La autonomía es **acotada**, no ilimitada.

---

## 5. Papel de MCP-Pi

MCP-Pi es la frontera de confianza entre IA e infraestructura local.

Su responsabilidad canónica es:

```text
autenticar
→ validar
→ autorizar
→ limitar
→ delegar
→ auditar
→ recuperar
```

La Raspberry Pi no debe convertirse en una máquina de cómputo pesado ni en un host de modelos LLM. El trabajo real se delega a Targets.

MCP-Pi debe permanecer disponible como appliance de bajo consumo, independientemente de que un PC de administración esté encendido.

---

## 6. Principios de diseño

### KISS

**KISS — Keep It Simple, Stupid! («¡Mantenlo sencillo, estúpido!»).**

Preferir la solución mínima que cumpla seguridad, autonomía y mantenibilidad.

### Reuse First

Orden preferido:

```text
estándar oficial
→ SDK / herramienta oficial
→ herramienta del sistema
→ componente pequeño y maduro
→ código propio
```

No reinventar capacidades que OpenAI, MCP, OpenSSH, systemd o el sistema operativo ya proporcionen correctamente.

### Infraestructura propia

La operación básica de MCP-Pi no debe depender obligatoriamente de un servicio privado de terceros equivalente a Desktop Commander.

Un servicio externo puede usarse como herramienta auxiliar o temporal, pero no debe ser una pieza irremplazable del camino productivo si existe una alternativa oficial/autohospedada razonable.

### Privacidad y control

No exponer puertos domésticos públicamente por defecto.

Mantener secretos fuera de Git.

Usar canales oficiales seguros cuando se requiera entrada desde servicios cloud.

### Least Privilege / Deny by Default / Fail Closed

Cada cliente sólo ve y ejecuta lo explícitamente autorizado.

Un fallo de identidad, autenticación, política o ambigüedad debe detener la operación en lugar de relajar controles.

### Herramientas de alto nivel antes que shell arbitraria

La interfaz principal hacia IA debe expresar intención mediante herramientas controladas, por ejemplo:

```text
target_status
read_file
git_status
run_task
write_file
gateway_doctor
gateway_backup
gateway_maintenance
gateway_reboot
```

No convertir MCP-Pi en `run_anything`, `bash`, `powershell` o una shell remota sin restricciones como contrato principal.

Si una nueva capacidad es necesaria, preferir una herramienta estrecha, auditable y explícita.

### Multi-target desde el diseño

`termux-main` es el primer worker real, no el límite de la arquitectura.

El Gateway debe poder incorporar, retirar o cambiar targets Windows, Linux, Android u otros sin convertir IP o MAC en identidad.

---

## 7. Qué significa “autonomía” en este proyecto

Autonomía NO significa que la IA pueda hacer cualquier cosa.

Significa que, dentro de un objetivo y permisos explícitos, pueda cerrar ciclos completos sin intervención manual innecesaria:

```text
observar
→ decidir
→ actuar
→ verificar
→ continuar
```

Debe escalar al usuario cuando:

- una operación queda fuera de grants;
- existe riesgo destructivo no aprobado;
- requiere credenciales o secretos no disponibles;
- la identidad de un target no puede demostrarse;
- existe ambigüedad real;
- se requiere una decisión de producto/arquitectura;
- continuar podría violar una política explícita.

---

## 8. Modelo objetivo de conectividad

La meta final para ChatGPT es:

```text
ChatGPT / OpenAI
        │
        │ conectividad MCP oficial y segura
        ▼
MCP-Pi
        │
        │ políticas + routing + auditoría
        ▼
Targets privados
```

Una ruta local como:

```text
Codex / ChatGPT Desktop
→ MCP stdio sobre SSH
→ MCP-Pi
```

es válida y útil como cliente local o prueba E2E, pero NO sustituye el objetivo estratégico de permitir que un producto OpenAI autorizado pueda alcanzar el appliance de manera remota y segura sin que el usuario opere manualmente el puente.

Cuando el acceso provenga de OpenAI cloud, preferir mecanismos oficiales como Secure MCP Tunnel u otra capacidad oficial vigente antes de crear túneles propietarios.

Las capacidades, planes y entitlement de OpenAI cambian con el tiempo y deben revalidarse con documentación oficial antes de implementar o declarar un gate permanente.

---

## 9. Estado de la visión

### Nivel 1 — Local MCP

```text
Cliente IA local
→ MCP-Pi
→ Target
```

**Estado:** infraestructura local esencial completada y validada en `v1.2.0`.

### Nivel 2 — OpenAI Remote MCP

```text
OpenAI cloud
→ canal MCP oficial seguro
→ MCP-Pi
→ Target
```

**Estado:** siguiente objetivo estratégico. La parte local está preparada; falta demostrar el E2E remoto con acceso/credenciales oficiales disponibles.

### Nivel 3 — Autonomía operativa

```text
Usuario define objetivo
→ ChatGPT inspecciona
→ actúa mediante MCP-Pi
→ valida
→ continúa
→ sólo consulta al usuario cuando corresponde
```

**Estado:** visión final. Su aceptación requiere un flujo E2E real y repetible, no sólo conectividad teórica.

---

## 10. Acceptance test de la visión

La meta no se considera cumplida sólo porque `tools/list` funcione.

El acceptance representativo es:

```text
Desde un producto OpenAI autorizado
→ sin copiar comandos manualmente
→ consultar MCP-Pi
→ localizar y acceder a un target autorizado
→ inspeccionar un proyecto
→ ejecutar una tarea autorizada
→ leer el resultado
→ decidir automáticamente el siguiente paso
→ verificar el resultado
→ continuar o escalar al usuario según política
```

Debe mantenerse:

- identidad criptográfica;
- grants;
- deny-by-default;
- auditoría;
- ausencia de shell arbitraria como interfaz principal;
- recuperación ante fallos razonables;
- independencia del PC del usuario para la operación normal del gateway.

---

## 11. Criterio para trabajo futuro

Antes de aceptar una nueva feature, responder:

> **¿Acerca realmente MCP-Pi al modelo donde el usuario define objetivos y supervisa, mientras la IA puede ejecutar ciclos autorizados de forma segura y autónoma?**

Si no, la feature debe justificar claramente por qué es necesaria.

Este documento define la misión estratégica. `AGENTS.md` conserva las reglas operativas, `docs/project-state.md` el estado actual y los documentos de release/Git conservan la evidencia histórica.
