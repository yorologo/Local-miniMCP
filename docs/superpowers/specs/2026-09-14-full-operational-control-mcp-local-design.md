# Design Document: Full Operational Control for MCP_Local & Termux Environment Administration

**Date:** 2026-09-14  
**Status:** Approved  
**Target Client:** `chatgpt-main` (with `capability: "*"`)  
**Target Appliance:** MCP-Pi Gateway (Raspberry Pi Model A+, Debian 13 Trixie)  
**Target Worker:** `termux-main` (Android 16 / Termux `u0_a435`)  
**Project Scope:** `/data/data/com.termux/files/home/Projects/test/MCP_Local`

---

## 1. Contexto y Objetivos

El objetivo de este diseño es dotar a `chatgpt-main` de **control operativo total** para desarrollar, depurar, compilar, testear y administrar el proyecto `MCP_Local` y su entorno de soporte en Termux, satisfaciendo simultáneamente dos invariantes fundamentales:
1. **Confinamiento Ordinario del Filesystem:** Las herramientas directas de manipulación de archivos y directorios operan exclusivamente dentro del árbol del proyecto `/data/data/com.termux/files/home/Projects/test/MCP_Local`, previniendo *path traversal*, *symlink escapes* o accesos directos arbitrarios a otros proyectos en `$HOME`.
2. **Ejecución y Administración del Entorno Termux:** A través de una nueva herramienta MCP de primer nivel (`run_command`), el agente dispone de ejecución completa en shell de Termux, permitiendo la instalación, actualización y gestión de dependencias y paquetes (`pkg`, `apt`, `pip`, `npm`, `npx`), el uso irrestricto de Git, invocación de compiladores (`clang`), runtimes (`node`, `python`), frameworks de prueba (`pytest`) y gestión de procesos, sin confundir el directorio de trabajo (`cwd`) con los permisos del ejecutable ni bloquear efectos legítimos de gestores de paquetes en `$PREFIX`.

---

## 2. Catálogo de Herramientas MCP y Separación de Scopes

### 2.1 Herramientas de Filesystem del Proyecto (Scope Confinado)
Todas las herramientas directas de filesystem exigen validación estricta de ruta mediante `validate_path` y `validate_canonical_path` contra el root de `MCP_Local`:

| Herramienta | Función | Parámetros Clave | Scope Permitido |
|---|---|---|---|
| `read_file` | Lee archivo UTF-8 | `path`, `offset`, `limit` | Confinado a `MCP_Local` |
| `write_file` | Escribe/crea atómicamente | `path`, `content`, `create`, `expected_sha256` | Confinado a `MCP_Local` |
| `append_file` | Añade contenido al final | `path`, `content` | Confinado a `MCP_Local` |
| `delete_file` | Elimina archivo o directorio vacío | `path` | Confinado a `MCP_Local` (raíz protegida) |
| `copy_file` | Copia archivo | `source_path`, `dest_path` | Ambos dentro de `MCP_Local` |
| `move_file` | Mueve/renombra archivo | `source_path`, `dest_path` | Ambos dentro de `MCP_Local` |
| `mkdir` | Crea directorio | `path`, `parents` | Confinado a `MCP_Local` |
| `list_directory` | Lista contenido | `path`, `recursive` | Confinado a `MCP_Local` |
| `file_stat` | Metadatos de archivo/carpeta | `path` | Confinado a `MCP_Local` |
| `search` | Búsqueda por patrón/texto | `pattern`, `path`, `is_regex` | Confinado a `MCP_Local` |

### 2.2 Herramienta de Ejecución: `run_command`
Permite ejecución estructurada en el Target Worker (`termux-main`) mediante shell interactivo de Termux:

* **Parámetros (`inputSchema`):**
  * `command` (*string, required*): Comando o pipeline shell a ejecutar.
  * `cwd` (*string, optional*): Directorio inicial de trabajo. Por defecto: raíz del proyecto `MCP_Local`. Si se especifica relativo, se resuelve relativo a `MCP_Local`.
  * `env` (*object, optional*): Pares clave-valor de variables de entorno adicionales.
  * `timeout` (*integer, optional*): Timeout en segundos (por defecto: 30s, configurable hasta límites seguros del appliance).
  * `stdin` (*string, optional*): Contenido opcional para enviar a stdin.

* **Estructura de Retorno:**
  * `stdout` (*string*): Salida estándar capturada (acotada a `max_output_bytes`).
  * `stderr` (*string*): Salida de error estándar capturada.
  * `exit_code` (*integer*): Código de retorno del proceso.
  * `timed_out` (*boolean*): Indica si el proceso excedió el tiempo límite.
  * `duration` (*number*): Tiempo de ejecución en segundos con precisión de ms.
  * `effective_cwd` (*string*): Ruta absoluta real donde arrancó la ejecución.

---

## 3. Matriz de Autorización, Políticas y Clasificación de Entorno

### 3.1 Modelo de Capabilities
Se amplía la jerarquía de capacidades en `policy.py`:
* `read`: Herramientas de consulta y lectura de archivos dentro del proyecto.
* `write`: Modificación, creación, eliminación, movimiento y copiado de archivos dentro del proyecto.
* `execute`: Ejecución de tareas de proyecto (`run_task`) y comandos (`run_command`).
* `environment_management`: Capacidad genérica para administración del entorno de desarrollo y gestores de paquetes (`pkg`, `apt`, `pip`, `npm`, `npx`, etc.).
* `admin`: Herramientas de telemetría y ciclo de vida del Gateway (`gateway_*`).
* `*`: **Super-capability** que engloba automáticamente todas las capacidades anteriores. `chatgpt-main` con `capability: "*"` dispone de acceso completo a todos los vectores autorizados.

### 3.2 Separación entre Intención de Acceso a Archivos y Efectos de Sistema
El Policy Engine aplica dos reglas diferenciadas:
1. **Regla de Operaciones de Entorno Legítimas:**
   Cuando se ejecuta un gestor oficial de paquetes o herramientas de desarrollo (`pkg`, `apt`, `pip`, `npm`, `git`, `python`, `clang`, `pytest`), estos procesos tienen permiso para leer y escribir en sus ubicaciones estándar del sistema Termux (`$PREFIX`, `site-packages`, directorios de caché en `$TMPDIR` o `~/.cache`, `node_modules` globales en `$PREFIX/lib/node_modules`, etc.).
2. **Regla de Confinamiento de Intención en Shell:**
   Para comandos directos de manipulación de archivos (`cat`, `rm`, `cp`, `mv`, `nano`) invocados desde el shell, el Policy Engine valida que la intención no apunte arbitrariamente a otros proyectos privados en `$HOME` ajenos a `MCP_Local` y ajenos a las rutas legítimas del sistema.

---

## 4. Preservación del Entorno Termux y Manejo de Binarios

En `ssh_transport.py` y en la invocación remota en `termux-main`:
1. **Entorno Heradado Obligatorio:**
   * `HOME=/data/data/com.termux/files/home`
   * `PREFIX=/data/data/com.termux/files/usr`
   * `PATH=$PREFIX/bin:$PREFIX/bin/applets:$PATH`
   * `TMPDIR=$PREFIX/tmp`
   * `LANG=en_US.UTF-8`
   * `TERMUX_VERSION=0.118.3`
2. **Shell de Ejecución:**
   `/data/data/com.termux/files/usr/bin/bash` o `$SHELL -c` garantizando el soporte de `&&`, `||`, `;`, `|`, subshells `$()`, variables y redirecciones.
3. **Manejo No Interactivo de Paquetes:**
   Flags sugeridos o auto-inyectados para operaciones de actualización/instalación (`-y` en `apt`/`pkg`, `--no-input` en `pip`, `-y` en `npm`) para evitar bloqueos por prompts interactivos no atendidos.
4. **Restricción No-Root:**
   Las operaciones se ejecutan estrictamente bajo el UID no-root de Termux (`u0_a435`). No se solicitan privilegios de superusuario ni se alteran políticas de SELinux.

---

## 5. Implementación en los Componentes del Sistema

1. **Python Gateway Core (`src/mcp_gateway/`):**
   * `policy.py`: Registro de nuevas herramientas en `TOOL_CAPABILITIES`, definición de `environment_management`, soporte de capability `*`.
   * `tools.py`: Implementación de métodos `run_command`, `append_file`, `delete_file`, `copy_file`, `move_file`, `mkdir`, `search`.
   * `bridge.py`: Exposición de los nuevos métodos mediante el CLI de bridge serializado por JSON.
   * `ssh_transport.py`: Método para ejecución de comandos con captura de `stdout`, `stderr`, `exit_code`, timeout y medición de duración.
2. **Go MCP Adapter (`mcp-adapter/`):**
   * `server.go`: Registro en `allKnownTools`, schemas en `registerToolByName`, y forward al bridge de Python.
   * Compilación cruzada para ARMv6 (`scripts/build-armv6.sh`) y despliegue del binario en la Raspberry Pi.
3. **Appliance Deployment & Runtime:**
   * Actualización del código fuente en la Raspberry Pi `/home/mcp-gateway/mcp-gateway/src`.
   * Despliegue del binario Go compilado `bin/mcp-gateway-adapter-linux-armv6`.
   * Reinicio de `mcp-gateway-mcp.service` y verificación de `systemctl status` y `/live`.

---

## 6. Plan de Validación y Criterios de Aceptación

1. **Validación de Filesystem Confinado:**
   * Comprobar que `pwd` y `effective_cwd` inician en `/data/data/com.termux/files/home/Projects/test/MCP_Local`.
   * Crear, leer, modificar y eliminar `.mcp_scope_test` vía MCP tools.
   * Verificar rechazo de `..` traversal hacia directorios externos.
2. **Validación de Ejecución:**
   * Ejecutar `python -c "print('MCP_EXEC_OK')"` vía `run_command` y verificar `exit_code: 0`, `stdout: "MCP_EXEC_OK\n"`.
3. **Validación Git:**
   * Crear archivo temporal de prueba en el proyecto, ejecutar `git add`, verificar con `git status --short` y limpiar sin alterar trabajo existente.
4. **Validación de Package Management:**
   * Inspección no destructiva de gestores: `pkg --version`, `apt --version`, `python -m pip --version`, `npm --version`.
   * Verificación de que la política del Gateway autoriza operaciones de entorno.
5. **Validación de Parada de Emergencia:**
   * Confirmar que el Kill Switch global y el interruptor de escritura del proyecto continúan funcionando y revocan operaciones de inmediato si se activan.
6. **Diagnóstico Integral:**
   * Ejecutar `mcp-gateway doctor` y suite de pruebas unitarias/regresión con 100% PASS.
