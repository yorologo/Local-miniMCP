# Phase 5: Controlled Write Architecture & Security Specifications

## 1. Visión General

La Fase 5 incorpora capacidades de mutación controlada al Gateway MCP (`write_file`), preservando el 100% de las garantías de aislamiento, mínimo privilegio y deny-by-default establecidas en las Fases 4A, 4B y 4C.

El Go MCP Adapter actúa estrictamente como puente de protocolo/serialización y **no** contiene autoridad de filesystem, validación de rutas ni políticas de seguridad. Toda la autoridad de decisión reside en Python Gateway Core.

---

## 2. Arquitectura de Flujo de Escritura

```text
       MCP Client (Claude / ChatGPT / Gemini)
                         │
                         ▼ Streamable HTTP / Stdio
       Go MCP Adapter (mcp-gateway-adapter)
                         │
                         ▼ CLI invocation (subprocess JSON)
       Python Bridge (mcp_gateway.bridge)
                         │
                         ▼
       Python Gateway Core (mcp_gateway.tools)
                         │
       ┌─────────────────┴─────────────────┐
       ▼                                   ▼
  Global Policy                       Project Policy
  writes_enabled == true?             project.write == true?
       │                                   │
       └─────────────────┬─────────────────┘
                         ▼
                  Path Validation
                  - Canonical root confinement
                  - Traversal denial (..)
                  - Symlink target denial (SYMLINK_WRITE_DENIED)
                  - Symlink parent denial
                  - Size enforcement (max_write_bytes)
                  - Encoding validation (UTF-8 strict, NO NUL \0)
                         │
                         ▼
                  Preconditions & Hash Lock
                  - If overwrite: expected_sha256 matches?
                  - If create=true: file does NOT exist?
                         │
                         ▼
                  Gateway Backup
                  - Retained in ~/.local/share/mcp-gateway/backups/
                  - Up to 5 rolling versions per file
                         │
                         ▼ SSH Transport (mcp-gateway @ MCP-Pi)
                  Atomic Write on Target Worker
                  - tempfile.mkstemp in parent dir
                  - fsync temp file
                  - chmod (preserve existing mode)
                  - os.replace (atomic inode swap)
                  - fsync parent dir
                  - cleanup temp on any error
                         │
                         ▼
                  Target Worker File System
```

---

## 3. Estado de Herramientas de Mutación

- **`write_file`**: **OPERATIVA Y VERIFICADA**.
  - Soporta creación de archivos (`create=true`).
  - Soporta sobreescritura protegida por hash (`expected_sha256`).
  - Soporta modo simulación sin mutación (`dry_run=true`) retornando `unified_diff`.
  - Backups automáticos en el Gateway antes de sobreescribir.
- **`apply_patch`**: **APPLY_PATCH: DEFERRED_FOR_SAFE_IMPLEMENTATION**.
  - Razón técnica: Conforme a los principios KISS y a la directiva de seguridad del proyecto, un parser y aplicador de diffs de múltiples hunks sin dependencias externas (`patch` binario no uniforme entre Android Termux, Linux y Windows) incrementa la superficie de ataque y riesgo de corrupción parcial. La combinación de `read_file` (que expone SHA256) y `write_file` atómico con `expected_sha256` proporciona una alternativa determinista, libre de condiciones de carrera y completamente segura.

---

## 4. Matriz de Códigos de Error de Escritura

| Código de Error | Causa | Nivel de Bloqueo |
| :--- | :--- | :--- |
| `WRITES_DISABLED` | El switch global `writes_enabled` en Registry está en `false`. | Gateway Core |
| `WRITE_NOT_ALLOWED` | El proyecto objetivo tiene `project.write = false`. | Policy Engine |
| `WRITE_CONFLICT` | El `expected_sha256` provisto no coincide con el hash actual del archivo remoto. Previene pérdida de actualizaciones / TOCTOU. | Precondición |
| `FILE_ALREADY_EXISTS` | Se especificó `create=true` pero el archivo ya existe en destino. | Precondición |
| `NOT_FOUND` | Se especificó `create=false` (sobreescritura) pero el archivo no existe. | Precondición |
| `SYMLINK_WRITE_DENIED` | La ruta destino o cualquiera de sus directorios padre es un enlace simbólico. | Path Security |
| `INVALID_PATH` | La ruta contiene componentes `..`, está vacía o resuelve fuera del root canónico del proyecto. | Path Security |
| `FILE_TOO_LARGE` | El contenido a escribir supera `max_write_bytes` (por defecto 256 KiB). | Resource Limit |
| `INVALID_ENCODING` | El contenido no es UTF-8 válido o contiene bytes nulos (`\x00`). | Data Hygiene |
| `WRITE_FAILED` | Fallo mecánico o de permisos durante la escritura/reemplazo en el worker. | Target System |

---

## 5. Control de Emergencia y Panic Button

En la consola administrativa (`127.0.0.1:8080/settings`):
- **Botón de Pánico**: `/settings/disable-writes` deshabilita de inmediato todas las mutaciones (`writes_enabled: false`) mientras preserva el 100% de las herramientas de lectura (`read_file`, `file_stat`, `list_directory`, etc.).
- **Kill Switch Global**: `/settings/kill-switch` bloquea absolutamente toda operación de clientes MCP.
- **Permisos por Proyecto**: En `/projects`, cada proyecto tiene su toggle individual para autorizar o revocar permisos de escritura.

---

## 6. Auditoría y Privacidad

- El registro de auditoría (`activity`) registra metadatos de escritura (`WRITE`, `DRY_RUN`, `DENY`): actor, acción, target, proyecto, bytes transferidos, sha256 antiguo y nuevo.
- **NUNCA** se almacena contenido de archivos ni diferencias completas en los logs de auditoría.
