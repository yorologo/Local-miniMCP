# Especificación y Documentación Técnica - Gateway MVP (Fase 4A: Gateway Core)

## 1. Resumen Ejecutivo

En la Fase 4A se ha implementado y verificado con éxito el **Gateway Core** en la Raspberry Pi Model A+ (`MCP-Pi`, `192.168.68.85`).

El núcleo del gateway:
- Está escrito exclusivamente con la **librería estándar de Python 3** (cero dependencias externas, cero pip, apt no modificado).
- Se ejecuta estrictamente bajo la cuenta de servicio sin privilegios **`mcp-gateway` (UID 1001)**.
- Implementa una arquitectura **multi-target** y **multi-proyecto** orientada a configuración desacoplada (`config/targets.local.json`), sin acoplamientos rígidos a sistemas operativos específicos.
- Ha sido validado en vivo contra el primer target real: `termux-main` (`192.168.68.84:8022`, Android 16 / Termux, usuario `u0_a435`).
- Cumple con una estricta política **deny-by-default** (bloqueo de traversal, resolución canónica remota con `realpath` frente a symlinks y prefijos hermanos, y ejecución restringida a tareas en lista blanca).

---

## 2. Arquitectura de Componentes

```text
[ Cliente / CLI / Futuro Adaptador MCP ]
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                       GATEWAY CORE                          │
│                   (mcp-gateway@MCP-Pi)                      │
│                                                             │
│  ┌─────────────────┐       ┌─────────────────────────────┐  │
│  │ GatewayConfig   │ ◄───► │ Policy Engine               │  │
│  │ (targets.json)  │       │ - Deny-by-default           │  │
│  └─────────────────┘       │ - Sintaxis relativa         │  │
│                            │ - Canonical realpath check  │  │
│                            │ - Task allowlisting         │  │
│                            └─────────────────────────────┘  │
│                                           │                 │
│  ┌─────────────────┐                      │                 │
│  │ GatewayTools    │ ─────────────────────┘                 │
│  │ (8 herramientas)│                                        │
│  └─────────────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ SSHTransport                                          │  │
│  │ - Subprocess nativo OpenSSH                           │  │
│  │ - Sin shell injection / shlex quote                   │  │
│  │ - Límite de bytes / detección de binarios             │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
              SSH (Alias: pc-local / termux-local)
              Clave: mcp_gateway_ed25519 (Ed25519)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  TARGET: termux-main                        │
│                (u0_a435@192.168.68.84:8022)                 │
│                                                             │
│  Project: MCP_Local                                         │
│  Root: /data/data/com.termux/files/home/Projects/test/...   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Principios de Seguridad y Políticas

### 3.1 Política Deny-by-Default
1. **Validación Sintáctica de Rutas Relativas**:
   - Se prohíben caracteres de control, bytes nulos (`\0`) y paths vacíos.
   - Se prohíben rutas absolutas (comenzando con `/`, `\`, `~` o letras de unidad tipo `C:`).
   - Se rechaza estrictamente cualquier componente `..` dentro de la ruta (`INVALID_PATH`).
2. **Validación Canónica Remota (Remote Canonical Path Check)**:
   - Toda ruta candidata dentro de un proyecto es resuelta canónicamente en el host remoto (`realpath -m`).
   - El resultado debe residir estrictamente dentro del directorio raíz autorizado del proyecto (`project.root`).
   - Se previenen escapes mediante enlaces simbólicos hacia carpetas del sistema (`escape_symlink -> $HOME`).
   - Se bloquean colisiones de prefijo hermano (ej. `/root-evil` cuando el root autorizado es `/root`).
3. **Ejecución Segura de Tareas (Allowlisted Tasks Only)**:
   - **No existe comando de shell arbitrario**.
   - Toda tarea ejecutable (`run_task`) debe estar explícitamente declarada en la configuración del proyecto con un vector estricto de argumentos `argv` (ej. `["git", "status", "--short"]`).
   - Las variables o comandos fuera de la lista blanca son rechazados inmediatamente (`TASK_NOT_ALLOWED`).
4. **Protección en Lectura de Archivos**:
   - Límite máximo configurable de lectura (por defecto 1 MiB).
   - Verificación de contenido binario: si el archivo contiene `\0`, se rechaza con `BINARY_FILE_NOT_SUPPORTED`.
   - Se verifica que el objetivo sea un archivo regular y no un directorio.

---

## 4. Catálogo de Herramientas Implementadas

Todas las herramientas emiten una respuesta estructurada y predecible en formato JSON con la siguiente estructura:

```json
{
  "ok": true,
  "tool": "nombre_herramienta",
  "duration_ms": 12,
  "result": { ... },
  "target": "termux-main",
  "project": "MCP_Local"
}
```

En caso de error:
```json
{
  "ok": false,
  "tool": "nombre_herramienta",
  "duration_ms": 3,
  "error": {
    "code": "INVALID_PATH | TASK_NOT_ALLOWED | UNKNOWN_TARGET | ...",
    "message": "Detalle explicativo del rechazo"
  },
  "target": "...",
  "project": "..."
}
```

### Herramientas del Core:
| Herramienta | Parámetros | Propósito |
|---|---|---|
| `health` | Ninguno | Estado local del gateway (hostname, versión, Python, config cargada). |
| `list_targets` | Ninguno | Lista de targets configurados y sus proyectos públicos autorizados. |
| `target_status` | `target` | Comprueba conectividad SSH, latencia y hostname del target remoto. |
| `list_directory` | `target`, `project`, `relative_path` | Lista archivos y carpetas dentro de la ruta relativa autorizada (hasta 200 entradas). |
| `file_stat` | `target`, `project`, `relative_path` | Retorna metadata (tamaño, tipo, timestamp de modificación `mtime`). |
| `read_file` | `target`, `project`, `relative_path` | Lee contenido de archivo de texto con límite de 1 MiB. |
| `git_status` | `target`, `project` | Ejecuta `git status --short` de forma segura en la raíz del proyecto. |
| `run_task` | `target`, `project`, `task` | Ejecuta una tarea predefinida en la lista blanca de la configuración. |

---

## 5. Matriz de Pruebas y Evidencia de Verificación

### 5.1 Pruebas Unitarias Remotas (MCP-Pi como `mcp-gateway`)
- **Total ejecutadas**: 28 pruebas
- **Aprobadas**: 28 / 28 (100%)
- **Tiempo de ejecución**: 0.201s
- **Módulos evaluados**: `test_config.py` (7 tests), `test_policy.py` (10 tests), `test_tools.py` (11 tests).

### 5.2 Pruebas en Vivo contra Target Real (`termux-main`)
| Prueba | Comando | Resultado | Duración |
|---|---|---|---|
| **1.1 Health** | `health` | PASS (`gateway_status: ok`, `MCP-Pi`) | 0 ms |
| **1.2 List Targets** | `list-targets` | PASS (`targets: [termux-main]`) | 0 ms |
| **1.3 Target Status** | `target-status termux-main` | PASS (`reachable: true`, `latency_ms: 780`) | 781 ms |
| **1.4 List Directory** | `list-directory termux-main MCP_Local .` | PASS (11 entradas listadas) | 3124 ms |
| **1.5 File Stat** | `file-stat termux-main MCP_Local README.md` | PASS (`size: 3894`, `exists: true`) | 3893 ms |
| **1.6 Read File** | `read-file termux-main MCP_Local README.md` | PASS (`size_bytes: 3894`, contenido íntegro) | 2150 ms |
| **1.7 Git Status** | `git-status termux-main MCP_Local` | PASS (`status_output: ?? .gitignore ...`) | 2244 ms |
| **1.8 Run Task** | `run-task termux-main MCP_Local git_status` | PASS (`exit_code: 0`, salida completa) | 1279 ms |

### 5.3 Pruebas Negativas de Seguridad
| Prueba Negativa | Vector Evaluado | Código de Rechazo | Mensaje Obtenido | Estado |
|---|---|---|---|---|
| **Traversal `..`** | `read-file ../.bashrc` | `INVALID_PATH` | `Parent directory traversal ('..') is not allowed` | **PASS** |
| **Ruta Absoluta** | `read-file /etc/passwd` | `INVALID_PATH` | `Absolute paths are not allowed` | **PASS** |
| **Tarea Arbitraria** | `run-task rm_rf` | `TASK_NOT_ALLOWED` | `Task 'rm_rf' is not allowlisted for this project` | **PASS** |
| **Target Desconocido** | `target-status unknown-box` | `UNKNOWN_TARGET` | `Target 'unknown-box' is not configured` | **PASS** |
| **Escape por Symlink** | `read-file escape_symlink/.bashrc` | `PATH_OUTSIDE_ALLOWED_ROOT` | `Path '...' resolves outside allowed root '...'` | **PASS** |

---

## 6. Estado del `MCP_SDK_GATE`

- **Evaluación**: El sistema base Raspbian 11 en la Raspberry Pi Model A+ no dispone de `pip` instalado (`python3-pip` no está presente).
- **Riesgo**: Instalar `pip` y el paquete oficial `mcp` requiere compilar ruedas o instalar herramientas pesadas (`rustc`, dependencias async complejas) que pueden agotar la memoria RAM de 176 MB utilizable y comprometer la estabilidad del sistema.
- **Dictamen**:
  - `MCP_SDK_GATE: DEFERRED`.
  - El Gateway Core es 100% independiente del SDK y funciona autónomamente con su CLI y su capa JSON.
  - Para la **Fase 4B (MCP Protocol Adapter)** se adoptará una de las siguientes opciones ligeras:
    1. Un adaptador stdio JSON-RPC nativo en Python stdlib que traduzca el protocolo MCP hacia el `GatewayTools`.
    2. Evaluación contenida de dependencias mínimas si se confirma compatibilidad sin saturar la memoria ni el disco.
