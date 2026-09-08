# MCP Raspberry Pi Gateway

Gateway MCP (Model Context Protocol) ligero, seguro y autónomo basado en una Raspberry Pi Model A+, diseñado para actuar como frontera de control, auditoría y orquestación entre ChatGPT y el entorno de trabajo remoto (Target Worker).

---

## 1. Propósito

El propósito de este proyecto es desacoplar el acceso de asistentes LLM (como ChatGPT) del entorno local primario de trabajo, interponiendo un nodo intermedio de hardware dedicado de bajo consumo (Raspberry Pi A+). 

La Raspberry Pi actúa como **orquestador y frontera de seguridad**:
- **Raspberry Pi**: Valida, autoriza, audita y canaliza peticiones. No corre LLMs ni compilaciones pesadas.
- **Target Worker**: Almacena repositorios y ejecuta procesos pesados bajo demanda auditada vía SSH/SFTP.

---

## 2. Arquitectura General

```text
[ ChatGPT ]
     |
     | MCP Seguro (Model Context Protocol)
     v
[ Raspberry Pi A+ Gateway ]  (192.168.68.85)
     |                       - Valida y audita políticas
     |                       - Aislamiento de red
     v SSH / SFTP seguro
[ Target Worker ]            (Cómputo pesado / Storage)
```

---

## 3. Principios Clave (KISS & Seguridad)

- **KISS (Keep It Simple, Stupid)**: Herramientas estándar, librerías del sistema y cero sobreingeniería.
- **Sin Docker**: Entorno nativo adaptado a ARMv6l y memoria contenida (176 MB RAM utilizables).
- **Mínimo Privilegio & Deny-by-default**: Accesos acotados y herramientas con parámetros estrictamente restringidos.
- **No exponer SSH a Internet**: Conexiones de administración exclusivamente en red local.
- **Protección de infraestructura preexistente**: Respeto total al Pi-hole de la red (`192.168.68.54`).

---

## 4. Estado Actual del Proyecto

| Fase | Descripción | Estado |
|---|---|---|
| **Fase 1: Línea Base Técnica** | Inventario completo de hardware, red, identidad, sudo y evaluación inicial | **COMPLETADA** |
| **Fase 2A: Identidad & Red** | Cambio a hostname `MCP-Pi`, resolución colisión, validación post-reboot y APT | **COMPLETADA** |
| **Fase 2B: Identidad Técnica Pi** | Creación de usuario `mcp-gateway` sin sudo y par de claves dedicado Ed25519 | **COMPLETADA** |
| **Fase 3: Canal Pi → PC** | Canal SSH unidireccional `pc-local` con clave exclusiva y workspace smoke | **COMPLETADA (PASS_WITH_LIMITATION)** |
| **Fase 4A: Gateway Core** | Núcleo modular multi-target en Python stdlib, políticas deny-by-default y 8 herramientas operativas | **COMPLETADA** |
| **Fase 4B: Consola Admin & Registro** | Consola Web en `127.0.0.1:8080` (Flask + Jinja2 + Tailwind), Registro SQLite persistente y Emergency Kill Switch | **COMPLETADA** |
| **Fase 4C: Adaptador MCP Oficial** | Adaptador de protocolo MCP con Go SDK oficial v1.7.0, stdio y Streamable HTTP (`127.0.0.1:8090`), 8 herramientas | **COMPLETADA** |
| **Fase 5: Escritura Controlada** | Mutaciones controladas atómicas (`write_file`), verificación precondicional SHA-256, backups locales rotativos en Gateway, dry-run y panic button | **COMPLETADA** |
| **Fase 4D: Compatibilidad, Seguridad & Ciclo de Vida** | Versionado de contratos (`compatibility.json`), protección Host/Origin (anti DNS rebinding), modelo de salud (/live, /ready, /health), Doctor & Safe Repair, CLI unificado (`mcp-gateway`), instalador y panel web `/maintenance` con HTMX | **COMPLETADA** |
| **Fase 6: Clientes AI Externos & ChatGPT** | Integración con ChatGPT, Claude Desktop, túneles seguros y perfiles de autenticación cliente | *Siguiente* |
| **Fase 7: Operación Estable & Resiliencia** | Hardening de red, rotación de claves, monitoreo continuo y recuperación ante desastres | *Futura* |

---

## 5. Administración y Acceso

- **Host objetivo**: `192.168.68.85` (`MCP-Pi`, MAC `8c:90:2d:ac:e5:c0`)
- **Acceso Administrativo**:
  ```bash
  ssh Yorologo@192.168.68.85
  ```
- **Consola Web de Administración**:
  ```bash
  ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85
  # Navegar a http://127.0.0.1:8080 (o /maintenance para diagnósticos)
  ```
- **Servidor de Protocolo MCP (Streamable HTTP)**:
  - Endpoint local: `http://127.0.0.1:8090/mcp`
  - Endpoint de salud: `http://127.0.0.1:8090/health` (también `/live`, `/ready`, `/server/discover`)
  - Servicio systemd: `mcp-gateway-mcp.service` (escuchando estrictamente en loopback)
- **Identidad de Servicio Gateway**: `mcp-gateway` (sin sudo, opera el canal SSH, el gateway core, la consola web y el adaptador MCP)
- **Credenciales locales**: El archivo local `.mcp-pi.local.env` almacena los datos de entorno local (ignorado por Git, no committear).

---

## 6. Documentación

La documentación detallada se encuentra en:
- [AGENTS.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/AGENTS.md): Reglas, directivas de seguridad e identidades operacionales.
- [docs/architecture.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/architecture.md): Diagramas de red, capas del gateway y roles de seguridad.
- [docs/project-state.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/project-state.md): Matriz de verificación y estado en tiempo real.
- [docs/compatibility.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/compatibility.md): Especificación de contratos versionados, protección Host/Origin y request IDs.
- [docs/lifecycle.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/lifecycle.md): Guía del CLI unificado, ciclo de vida, manifiestos, respaldos y reversión.
- [docs/runbooks/doctor.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/doctor.md): Manual operativo de diagnóstico y auto-reparación segura.
- [docs/runbooks/install.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/install.md): Manual de instalación automatizada e idempotente.
- [docs/runbooks/update-rollback.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/update-rollback.md): Manual de actualización y reversión de releases.
- [docs/runbooks/uninstall.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/uninstall.md): Manual de desinstalación limpia y purga de datos.
- [docs/controlled-write.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/controlled-write.md): Especificación técnica del modelo de escritura controlada, seguridad y políticas.
- [docs/runbooks/controlled-write-smoke-test.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/controlled-write-smoke-test.md): Manual de pruebas de humo y verificación de escrituras atómicas.
- [docs/runbooks/write-recovery.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/write-recovery.md): Manual de recuperación y restauración desde backups del Gateway.
- [docs/mcp-adapter.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/mcp-adapter.md): Especificación técnica del Adaptador Go MCP, schemas, transportes y puente.
- [docs/runbooks/mcp-smoke-test.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/mcp-smoke-test.md): Manual de pruebas de humo y verificación E2E del protocolo MCP.
- [docs/admin-console.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/admin-console.md): Especificación técnica de la Consola Web de Administración y Registro Persistente.
- [docs/gateway-mvp.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/gateway-mvp.md): Especificación técnica del Gateway MVP Core, herramientas y políticas.
- [docs/runbooks/admin-console.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/admin-console.md): Manual operativo de la consola web, túnel SSH y gestión de usuarios.
- [docs/runbooks/registry-backup-restore.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/registry-backup-restore.md): Manual de respaldo, restauración y rollback a JSON.
- [docs/runbooks/gateway-smoke-test.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/gateway-smoke-test.md): Manual de despliegue y pruebas del Gateway en MCP-Pi.
- [docs/runbooks/pi-to-pc-ssh.md](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/docs/runbooks/pi-to-pc-ssh.md): Manual operativo del canal SSH Pi → Target Worker y procedimiento de revocación.

