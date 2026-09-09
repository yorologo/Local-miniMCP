# Client Grants & Granular Authorization Policy

## 1. Esquema y Definición de Grants

El control de acceso en el Gateway MCP-Pi opera bajo una arquitectura **Deny-by-Default** basada en concesiones explícitas (*grants*).

### Esquema SQLite (`gateway.db`)
```sql
CREATE TABLE IF NOT EXISTS grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    permissions TEXT NOT NULL,
    targets TEXT NOT NULL,
    projects TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(client_id) REFERENCES ai_clients(client_id) ON DELETE CASCADE
);
```

- **`client_id`**: Identificador único del cliente de IA (e.g. `gemini-main`, `claude-desktop`).
- **`permissions`**: Lista JSON o separada por comas de capacidades (`read`, `execute`, `write`, o `*`).
- **`targets`**: Lista de identificadores de target autorizados (e.g. `["*"]` o `["pc-local"]`).
- **`projects`**: Lista de identificadores de proyectos autorizados (e.g. `["*"]` o `["smoke"]`).

---

## 2. Matriz de Permisos por Herramienta

| Herramienta | Permiso Requerido | Alcance Aplicado | Comportamiento si no Autorizado |
| :--- | :--- | :--- | :--- |
| `health` | Ninguno (o `read`) | Global (Gateway) | Oculta si cliente deshabilitado |
| `list_targets` | `read` | Targets permitidos | Filtra targets fuera de scope |
| `target_status` | `read` | Target específico | Deniega si target no está en grant |
| `list_directory`| `read` | Target + Proyecto | Deniega si project no está en grant |
| `file_stat` | `read` | Target + Proyecto | Deniega si project no está en grant |
| `read_file` | `read` | Target + Proyecto | Deniega si project no está en grant |
| `git_status` | `read` | Target + Proyecto | Deniega si project no está en grant |
| `run_task` | `execute` | Target + Proyecto | Oculta en `tools/list`; Error en llamada |
| `write_file` | `write` | Target + Proyecto | Oculta en `tools/list`; Denegado en llamada |

---

## 3. Doble Autorización para Operaciones de Escritura (`write_file`)

Para que un cliente pueda ejecutar `write_file`, deben cumplirse concurrentemente todas las siguientes condiciones:
1. **Cliente Activo**: `ai_clients.enabled == 1`.
2. **Grant de Escritura**: El cliente debe contar con un grant que incluya `write` o `*` que coincida con el target y proyecto solicitado.
3. **Escrituras Globalmente Habilitadas**: `settings.writes_enabled == 1` en la configuración general del Gateway.
4. **Proyecto Habilitado para Escritura**: `project.write == 1` en el registro del proyecto específico.
5. **No Kill Switch**: El target no debe tener activado el kill switch de emergencia.

Si cualquiera de estas condiciones es falsa, la operación se deniega inmediatamente (*fail-closed*), registrando el evento de auditoría correspondiente en SQLite.
