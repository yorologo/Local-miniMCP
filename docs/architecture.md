# Arquitectura MCP Raspberry Pi Gateway

## 1. Visión Conceptual

El objetivo del proyecto es establecer un Gateway MCP personal en una Raspberry Pi Model A+ que actúe como perímetro de seguridad, intermediario y orquestador entre ChatGPT y el entorno de trabajo remoto (Target Worker).

```text
+-------------------+
|      ChatGPT      |
+-------------------+
          |
          | MCP Seguro (Model Context Protocol)
          v
+-------------------+
|  Raspberry Pi A+  |  --> [Frontera de seguridad / Orquestador / Gateway Core]
|  (192.168.68.85)  |      Valida, autoriza, limita, orquesta, audita (Python stdlib)
+-------------------+
          |
          | SSH / SFTP (Controlado y restringido vía clave exclusiva Ed25519)
          v
+-------------------+
|   Target Worker   |  --> [Nodo de cómputo y almacenamiento pesado]
|                   |      Almacena, busca, compila, ejecuta, procesa
+-------------------+
```

---

## 2. Roles y Separación de Responsabilidades

### Raspberry Pi Model A+ (Gateway)
- **Frontera de seguridad**: Expone únicamente interfaces controladas y autorizadas hacia el cliente/agente LLM.
- **Orquestación y auditoría**: Registra las operaciones solicitadas, valida políticas de acceso y supervisa el tráfico.
- **Bajo consumo y aislamiento**: No ejecuta modelos LLM ni tareas pesadas de compilación o análisis intensivo de datos, adecuándose a sus recursos (CPU ARMv6 single-core, ~176 MB RAM utilizables).
- **Deny-by-default**: Todas las operaciones no explícitamente permitidas están denegadas.
- **Zero-External-Dependencies**: El núcleo opera al 100% sobre la librería estándar de Python 3, evitando sobrecarga en ARMv6 y protegiendo el sistema operativo Raspbian 11 de dependencias pesadas.

### Target Worker (Worker / Storage)
- **Cómputo pesado**: Ejecución de compilaciones, indexación de archivos grandes, ejecución de pruebas pesadas o contenedores.
- **Almacenamiento**: Persistencia principal de repositorios y proyectos.
- **Acceso controlado**: Recibe únicamente comandos u operaciones canalizadas a través del canal SSH auditado desde el Gateway.

---

## 3. Topología de Red y Dispositivos Relevantes

| Dispositivo / Rol | Dirección IP | Hostname | Interfaz Activa | Estado en el Proyecto |
|---|---|---|---|---|
| **Raspberry Pi Gateway** | `192.168.68.85` | `MCP-Pi` | `wlan0` (Wi-Fi USB RTL8188EUS) | **Objetivo activo del gateway** |
| **Raspberry Pi (Pi-hole)** | `192.168.68.54` | `YorPi` | N/A | **FUERA DEL ALCANCE** (Dispositivo crítico LAN; no tocar) |
| **Gateway LAN (Router)** | `192.168.68.1` | - | LAN | Router / Servidor DHCP local |
| **Target Primario (Worker)** | `192.168.68.84:8022` | `localhost` | Wi-Fi LAN | Target `termux-main` (Android 16 / Termux) |

> [!CAUTION]
> **Aislamiento de Pi-hole (`192.168.68.54`)**:
> La Raspberry Pi con IP `192.168.68.54` actúa como DNS/Pi-hole de la red local y conserva su hostname `YorPi`. Está totalmente fuera del alcance de este proyecto y NO debe ser modificada, reiniciada ni alterada por ningún agente.

> [!NOTE]
> **Colisión de Hostname Resuelta**:
> La colisión inicial fue resuelta en la Fase 2A renombrando la Raspberry del gateway a `MCP-Pi`. La Raspberry Pi-hole conserva su nombre `YorPi`. No existe conflicto de resolución local.

---

## 4. Arquitectura del Gateway Core (Fase 4A)

El Gateway Core reside en `/home/mcp-gateway/mcp-gateway` en la Raspberry Pi y está desacoplado del protocolo final y de la plataforma subyacente.

```text
[ Cliente / Interfaz / Adaptador de Protocolo ]
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│                      GATEWAY CORE                      │
│                                                        │
│  ┌──────────────────┐        ┌──────────────────────┐  │
│  │  GatewayConfig   │ ◄────► │    Policy Engine     │  │
│  │ (config/targets) │        │ (Deny-by-default)    │  │
│  └──────────────────┘        └──────────────────────┘  │
│                                          │             │
│  ┌──────────────────┐                    │             │
│  │   GatewayTools   │ ───────────────────┘             │
│  │  (8 herramientas)│                                  │
│  └──────────────────┘                                  │
│            │                                           │
│            ▼                                           │
│  ┌──────────────────┐                                  │
│  │   SSHTransport   │                                  │
│  │ (OpenSSH stdlib) │                                  │
│  └──────────────────┘                                  │
└────────────┬───────────────────────────────────────────┘
             │
             │ Conexión SSH segura vía alias OpenSSH
             ▼
[ Target Remoto: Linux / macOS / Windows / Android-Termux ]
```

### 4.1 Capas del Núcleo
1. **Configuración (`config.py`)**:
   - Soporte nativo para múltiples targets y múltiples proyectos por target.
   - Declaración de raíces autorizadas (`root`), capacidades permitidas (`read`, `tasks`, etc.) y tareas predefinidas en lista blanca con vectores `argv` estrictos.
2. **Motor de Políticas (`policy.py`)**:
   - **Sintaxis de rutas**: Rechazo de rutas absolutas, traversals (`..`), caracteres nulos y paths vacíos.
   - **Validación canónica remota**: Resolución con `realpath` en el target para garantizar que la ruta resuelta habite dentro del `root` del proyecto, previniendo escapes mediante enlaces simbólicos o colisiones de prefijos hermanos.
   - **Lista blanca de tareas**: Solo se pueden ejecutar comandos explícitamente declarados en la configuración.
3. **Transporte SSH (`ssh_transport.py`)**:
   - Invocación de `ssh` mediante `subprocess` estándar sin shells intermedios (`shell=False`).
   - Comillas seguras con `shlex.quote`.
   - Lector seguro de archivos de texto (límite de 1 MiB, aborto si se detectan bytes nulos binarios).
4. **Herramientas de Alto Nivel (`tools.py`)**:
   - Implementa: `health`, `list_targets`, `target_status`, `list_directory`, `file_stat`, `read_file`, `git_status`, `run_task`.
   - Respuestas uniformes en JSON con estado (`ok`), herramienta (`tool`), duración (`duration_ms`), resultado estructurado (`result`) o error estandarizado (`error`).

---

## 5. Implementación del Canal Seguro Pi → Target

```text
[ MCP-Pi Gateway ]                               [ Target Worker ]
(192.168.68.85)                                  (192.168.68.84)
Usuario: mcp-gateway (UID 1001, sin sudo)        Usuario: u0_a435 (App Android / Termux, sin root)
Clave: ~/.ssh/mcp_gateway_ed25519                Puerto: 8022
Alias: pc-local / termux-local                   Allowed Root: .../MCP_Local
        |                                                ^
        +================== SSH =========================+
                    (Ed25519 sin password)
```

- **Separación de privilegios en el Gateway**: El canal hacia el target se ejecuta exclusivamente desde la cuenta de servicio `mcp-gateway`, sin acceso a `sudo` ni credenciales administrativas de la Raspberry.
- **Entorno del Worker en PC**: Ejecutado en un sandbox Linux/Android sin privilegios de root (`u:r:untrusted_app_27`), con OpenSSH Server en el puerto 8022.
- **Alcance acotado**: Delimitado al root del proyecto para impedir modificaciones o lecturas imprevistas fuera del espacio asignado.

---

## 6. Registro Persistente y Consola de Administración (Fase 4B)

La Fase 4B introduce una capa de persistencia transaccional y una consola de gestión web protegida que se sitúa sobre el Gateway Core sin alterar sus garantías de seguridad:

```text
       [ Administrador ]
               │
               │ Túnel SSH (ssh -L 8080:127.0.0.1:8080)
               ▼
┌────────────────────────────────────────────────────────┐
│ MCP-Pi (127.0.0.1:8080)                                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Consola Web Admin (Flask + Jinja2)          │  │
│  │     - Estilos Tailwind CSS precompilados         │  │
│  │     - CSRF, HttpOnly, SameSite=Strict, CSP       │  │
│  │     - PBKDF2 password hash, Rate limiting        │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Registry Abstraction Layer             │  │
│  │                                                  │  │
│  │   ┌────────────────────┐   ┌─────────────────┐   │  │
│  │   │   SQLiteRegistry   │   │  JsonRegistry   │   │  │
│  │   │  (gateway.db 64K)  │   │   (Fallback)    │   │  │
│  │   └────────────────────┘   └─────────────────┘   │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │             Gateway Core (tools.py)              │  │
│  │  - Emergency Kill Switch (gateway_enabled)       │  │
│  │  - Target / Project Enable / Disable check       │  │
│  │  - Deny-by-default Policy Engine                 │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           SSHTransport (Subprocess)              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────┬──────────────────────────┘
                              │
                              │ SSH Ed25519
                              ▼
                       [ Target Worker ]
```

### 6.1 Capa de Registro Abstraída
- **`RegistryBase` (ABC)**: Interfaz uniforme para operaciones de consulta y mutación.
- **`SQLiteRegistry`**: Almacén principal en `/home/mcp-gateway/.local/share/mcp-gateway/gateway.db`. Consultas 100% parametrizadas (`?`), control de versión de esquema con `PRAGMA user_version = 1`.
- **`JsonRegistry`**: Adaptador compatible hacia atrás para `config/targets.local.json`.
- **Rollback transparente**: La variable de entorno `MCP_GATEWAY_REGISTRY=json|sqlite` permite alternar de backend instantáneamente sin cambios de código.

### 6.2 Consola Web de Administración
- **Aislamiento de Red**: Escucha estrictamente en `127.0.0.1:8080`, inaccesible directamente por la LAN (`192.168.68.85`).
- **Zero Node.js en Raspberry Pi**: El CSS de Tailwind (17 KB) se compila en el entorno de desarrollo y se despliega como activo estático estricto.
- **Operaciones Core Auditas**: La consola invoca `GatewayTools` para pruebas y diagnósticos; nunca ejecuta comandos SSH arbitrarios desde los controladores web.
- **Interruptor de Emergencia (Emergency Kill Switch)**: Corta globalmente el acceso de las herramientas a los targets en milisegundos actualizando `gateway_enabled = false` en la base de datos.

---

## 7. Adaptador de Protocolo MCP Oficial (Fase 4C)

La Fase 4C expone las capacidades del Gateway Core a clientes compatibles con Model Context Protocol (MCP) mediante un adaptador de protocolo dedicado implementado con el SDK oficial de Go (`github.com/modelcontextprotocol/go-sdk` v1.7.0).

```text
┌────────────────────────────────────────────────────────┐
│                   Cliente MCP (LLM)                    │
│             (Claude Desktop, Cursor, etc.)             │
└───────────────────────────┬────────────────────────────┘
                            │
              JSON-RPC 2.0  │ (stdio ó Streamable HTTP)
                            ▼
┌────────────────────────────────────────────────────────┐
│ MCP-Pi (127.0.0.1:8090)                                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │   Adaptador MCP Oficial en Go                    │  │
│  │   (mcp-gateway-adapter)                          │  │
│  │   - Protocolo MCP 2026-07-28 (compat 2025-11-25) │  │
│  │   - Esquemas JSON Schema de 8 herramientas       │  │
│  │   - Transportes: stdio & Streamable HTTP         │  │
│  │   - Binario estático compilado para ARMv6 (8 MB) │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│        Invocación Bridge    │ CLI JSON (stdout/stderr) │
│        python3 -m bridge    │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │   Puente Python Gateway (bridge.py)              │  │
│  │   - Deserializa argumentos JSON                  │  │
│  │   - Consulta Registry (SQLite / JSON)            │  │
│  │   - Invoca GatewayTools con Policy Engine        │  │
│  │   - Devuelve resultado o error estandarizado     │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │   Policy Engine + Registry + SSHTransport        │  │
│  │   - Emergency Kill Switch global & por target    │  │
│  │   - Validación de rutas canónicas (realpath)     │  │
│  │   - Tareas predefinidas en lista blanca          │  │
│  └──────────────────────────┬───────────────────────┘  │
└─────────────────────────────┼──────────────────────────┘
                              │
                              │ SSH Ed25519 (mcp-gateway)
                              ▼
                       [ Target Worker ]
```

### 7.1 Separación Estricta de Responsabilidades

| Responsabilidad | Adaptador Go (`mcp-adapter`) | Núcleo Python (`mcp_gateway`) |
|---|---|---|
| **Protocolo MCP** | Handshake, negociación de versión, JSON-RPC 2.0 | Desacoplado de MCP (agnóstico de protocolo) |
| **Definición de Schemas** | Esquemas formales JSON Schema para 8 herramientas | Define tipos y docstrings de métodos |
| **Transportes** | Framing stdio y Streamable HTTP (`/mcp` con chunked SSE) | Subproceso CLI invoked on-demand |
| **Serialización** | Validación sintáctica de inputs MCP y wrapping de respuestas | Estructuras de datos Python a JSON nativo |
| **Seguridad y Políticas** | NINGUNA (no toma decisiones de autorización) | **AUTORIDAD ÚNICA**: validación de rutas, traversal, allowlists |
| **Kill Switch** | No almacena estado de seguridad | Evaluado en cada invocación contra `gateway.db` |
| **Conexiones SSH** | NINGUNA (no maneja credenciales ni claves SSH) | Invocación `ssh` segura con usuario `mcp-gateway` |

### 7.2 Protocolo y Transportes Soportados

1. **Stdio**:
   - Lectura de mensajes JSON-RPC por `stdin` y emisión por `stdout`.
   - Ideal para clientes locales (CLI, scripts, subprocesos de herramientas locales).
   - Flag: `-transport stdio`.
2. **Streamable HTTP**:
   - Escucha en `127.0.0.1:8090/mcp`.
   - Endpoint de salud en `GET /health` (retorna `{"status":"ok"}`).
   - Protocolo streaming basado en SSE (Server-Sent Events) cuando el cliente solicita `Accept: application/json, text/event-stream`.
   - Respuestas chunked con eventos de protocolo MCP.
   - Flag: `-transport http -bind 127.0.0.1:8090`.

### 7.3 Interfaz de Puente (Bridge)

La comunicación entre el adaptador Go y el Gateway Core se realiza a través de la CLI del puente `bridge.py`:
```bash
python3 -m mcp_gateway.bridge invoke <tool_name> '<json_arguments>'
```
- **Entrada**: Nombre de la herramienta y un string JSON con sus argumentos.
- **Salida**: JSON estructurado en `stdout`:
  - En caso exitoso: `{"ok": true, "result": {...}, "tool": "...", "duration_ms": ...}`
  - En caso de error: `{"ok": false, "error": {"code": "...", "message": "..."}, "tool": "..."}`
- **Códigos de salida**:
  - `0`: Ejecución exitosa de la herramienta.
  - `1`: Error controlado devuelto por la herramienta (política, archivo no encontrado, timeout, etc.).
  - `2`: Error de sintaxis en argumentos o fallo interno del puente.

### 7.4 Servicio del Sistema e Integración Operacional

- **Servicio systemd**: `mcp-gateway-mcp.service` activo y habilitado en el arranque.
- **Usuario de ejecución**: `User=mcp-gateway`, `Group=mcp-gateway` (sin privilegios de root ni sudo).
- **Consumo de memoria**: ~10 MiB RSS en la Raspberry Pi Model A+.
- **Monitoreo en Consola Admin**: La consola web de administración (`127.0.0.1:8080`) verifica en tiempo real la conectividad contra el socket del adaptador en `127.0.0.1:8090` y muestra el estado en el Dashboard.

---

## 8. Modelo de Escritura Controlada (Fase 5)

La Fase 5 introduce la capacidad de mutación controlada en targets remotos mediante la herramienta `write_file`, manteniendo inquebrantable el principio deny-by-default y protegiendo el sistema contra desbordamientos, colisiones concurrentes (TOCTOU) y escrituras destructivas.

```text
┌────────────────────────────────────────────────────────┐
│                   Cliente MCP (LLM)                    │
└───────────────────────────┬────────────────────────────┘
                            │ write_file(target_id, project_id, path,
                            │            content, expected_sha256, create, dry_run)
                            ▼
┌────────────────────────────────────────────────────────┐
│ MCP-Pi (127.0.0.1:8090)                                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │   Adaptador MCP en Go (mcp-gateway-adapter)      │  │
│  │   - Valida esquema de parámetros de write_file   │  │
│  │   - Pasa stdin/stdout al puente Python           │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │ CLI Bridge: python3 -m mcp_gateway.bridge
│                             ▼
│  ┌──────────────────────────────────────────────────┐  │
│  │   Gateway Core & Policy Engine (Python)          │  │
│  │                                                  │  │
│  │   1. Kill Switch Check (gateway_enabled == true) │  │
│  │   2. Dual-Key Check (writes_enabled && project)  │  │
│  │   3. Path Confinement (relativo, sin traversal)  │  │
│  │   4. Content Encoding (UTF-8 estricto, sin NUL)  │  │
│  │   5. Probe Remoto (SSH: realpath, existe, tipo)  │  │
│  │   6. Symlink Check (bloquea enlaces simbólicos)  │  │
│  │   7. Hash Lock Check (expected_sha256 / create)  │  │
│  │   8. Dry-Run Check (retorna diff si dry_run=true)│  │
│  │   9. Local Rolling Backup (Gateway ~/.local/...) │  │
│  │  10. Atomic Write (temp file -> fsync -> os.rep) │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │ Safe stdin piping (shlex.quote)
│                             ▼
│  ┌──────────────────────────────────────────────────┐  │
│  │   SSHTransport (OpenSSH subprocess)              │  │
│  └──────────────────────────┬───────────────────────┘  │
└─────────────────────────────┼──────────────────────────┘
                              │ SSH Ed25519 (mcp-gateway)
                              ▼
                       [ Target Worker ]
                       - Escritura en `.tmp_write_*`
                       - `os.replace` atómico en directorio padre
```

### 8.1 Garantías de Seguridad y Control

1. **Autorización con Doble Llave (Dual-Key Authorization)**:
   - **Llave Global**: `writes_enabled = true` en la tabla `settings` del Gateway (`SQLiteRegistry`). Por defecto está desactivada (`false`).
   - **Llave por Proyecto**: `project.write = true` en la configuración del proyecto específico. Si un proyecto solo tiene `read = true`, cualquier intento de escritura es denegado con `WRITE_NOT_ALLOWED`.

2. **Bloqueo Precondicional de Hash (Optimistic Concurrency / TOCTOU Protection)**:
   - Toda sobreescritura de un archivo existente **requiere** el parámetro `expected_sha256`. Si el contenido remoto ha cambiado o no coincide, la operación se aborta de inmediato con código `WRITE_CONFLICT`.
   - Para creación de archivos nuevos (`create = true`), el motor falla explícitamente con `FILE_ALREADY_EXISTS` si el destino ya existe.

3. **Confinamiento de Rutas y Rechazo de Enlaces Simbólicos**:
   - Se rechazan rutas que apunten a un enlace simbólico (`SYMLINK_WRITE_DENIED`), ya sea el archivo destino o cualquier directorio ancestro dentro del proyecto.
   - La ruta canónica debe residir estrictamente dentro de la raíz permitida del proyecto.

4. **Atomicidad de Escritura y Consistencia en Disco**:
   - El contenido se escribe en un archivo temporal con prefijo `.tmp_write_` en el mismo directorio padre.
   - Se asegura la sincronización a disco (`fsync`), se preservan los permisos POSIX del archivo original y se ejecuta una sustitución atómica mediante `os.replace`.
   - Se realiza `fsync` sobre el directorio contenedor para persistir la entrada de directorio.

5. **Backups Locales Rotativos en el Gateway**:
   - Antes de modificar cualquier archivo remoto existente, el Gateway almacena una copia íntegra en `~/.local/share/mcp-gateway/backups/<target>/<project>/<timestamp>_<path>`.
   - Se conservan hasta 5 versiones históricas por archivo. Al estar en la Raspberry Pi, el historial de backups no puede ser alterado o borrado desde el Target Worker.

6. **Modo Dry-Run**:
   - Si `dry_run = true`, el Gateway realiza todas las validaciones (autorización, hash precondicional, límites) y genera un `unified diff` entre el contenido existente y el nuevo, devolviéndolo sin aplicar ninguna modificación en el target.

7. **Botón de Pánico (Writes Panic Button)**:
   - La consola web de administración incluye un control de emergencia en `/settings/disable-writes` que apaga instantáneamente todas las mutaciones en el sistema sin interrumpir las consultas ni las lecturas de herramientas de diagnóstico.

### 8.2 Decisión Arquitectónica sobre `apply_patch`

El diseño original contemplaba una herramienta `apply_patch` para aplicar diffs unificados. Tras evaluación técnica, se determinó:
- **`APPLY_PATCH: DEFERRED_FOR_SAFE_IMPLEMENTATION`**: Aplicar parches multi-hunk de manera remota introduce vulnerabilidades de parsing difuso (fuzzy matching), ambigüedad de codificación de finales de línea (CRLF vs LF) y riesgo de estado inconsistente entre plataformas.
- La combinación de `read_file` (que expone el `sha256` actual) junto con `write_file(expected_sha256=...)` proporciona a los modelos LLM un flujo de edición determinista, atómico y libre de condiciones de carrera sin añadir complejidad frágil al gateway.


