# MCP Gateway Compatibility & Security Contract Specification

## 1. Visión General

La Fase 4D establece las bases normativas, de compatibilidad y ciclo de vida para el Gateway MCP (`MCP-Pi`). Garantiza que todos los componentes (Go Adapter, Python Bridge, Gateway Core, SQLite Registry y clientes AI externos) interactúen mediante contratos versionados inmutables y defensas en profundidad estrictas.

---

## 2. Contratos de Versiones (`compatibility.json`)

El archivo [`compatibility.json`](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/compatibility.json) define las versiones de interfaz soportadas por el sistema:

```json
{
  "gateway_version": "0.6.0",
  "core_api_version": 1,
  "bridge_api_version": 1,
  "tool_catalog_version": 2,
  "registry_schema_version": 1,
  "mcp": {
    "sdk": "go-sdk",
    "version": "1.7.0",
    "protocol": "2026-07-28",
    "protocol_legacy": "2025-11-25",
    "transports": ["stdio", "streamable_http"]
  },
  "runtime": {
    "minimum_python": "3.9",
    "architectures": ["armv6l", "aarch64", "x86_64"]
  }
}
```

### Componentes y Roles
- **Gateway Version (`0.6.0`)**: Versión semántica global del Gateway.
- **Core API (`v1`)**: Interfaz interna en Python (`GatewayTools`).
- **Bridge API (`v1`)**: Protocolo CLI de invocación entre el Go Adapter y Python (`python3 -m mcp_gateway.bridge invoke <tool> <args>`).
- **Tool Catalog (`v2`)**: Catálogo determinista alfabético de 9 herramientas (`file_stat`, `git_status`, `health`, `list_directory`, `list_targets`, `read_file`, `run_task`, `target_status`, `write_file`).
- **Registry Schema (`v1`)**: Esquema de base de datos SQLite controlado con `PRAGMA user_version = 1`.
- **MCP Protocol (`2026-07-28`)**: Protocolo oficial MCP nativo soportado por el Go SDK v1.7.0, con compatibilidad regresiva negociada para `2025-11-25`.

---

## 3. Principio Fail-Closed (Fallo Seguro)

Si el adaptador Go detecta que el Python Bridge reporta una versión de API incompatible (`bridge_api_version != 1`), o si el runtime de Python no está disponible:
1. El servidor se niega a enrutar solicitudes y marca su estado como no disponible.
2. Las llamadas a herramientas MCP fallan de inmediato con error `ADAPTER_NOT_READY`.
3. El endpoint `/ready` responde con código HTTP `503 Service Unavailable`.

---

## 4. Trazabilidad de Peticiones de Extremo a Extremo (`request_id`)

Cada interacción iniciada a través del protocolo MCP genera o propaga un identificador de correlación `request_id` (formato `req-<random-hex>` o derivado del cliente):
1. **Go MCP Adapter**: Asigna o preserva el `request_id` en el contexto de la llamada.
2. **Python Bridge**: Recibe `--request-id` en el comando CLI `invoke`.
3. **Gateway Core**: Inyecta el `request_id` en la respuesta estructurada (`{"ok": ..., "request_id": ...}`) y en el registro de auditoría (`activity.detail`).
4. **SSH Transport**: Adjunta el `request_id` en los metadatos de telemetría de ejecución remota (`SSHTransportResult.request_id`).

---

## 5. Costura de Autorización para Clientes Futuros (`can_client_use_tool`)

Preparado para la Fase 6 (integración con ChatGPT y clientes AI externos), el motor de políticas implementa [`can_client_use_tool`](file:///data/data/com.termux/files/home/Projects/test/MCP_Local/src/mcp_gateway/policy.py):
- Consulta el registro SQLite para verificar si el cliente existe y está habilitado.
- Verifica si el cliente tiene permisos para invocar herramientas específicas (por ejemplo, permitir herramientas de lectura y restringir `write_file` o `run_task`).
- Deniega por defecto si el cliente está explícitamente deshabilitado (`CLIENT_UNAUTHORIZED`).

---

## 6. Protección contra DNS Rebinding y Spoofing de Origen

El servidor MCP Streamable HTTP incorpora middleware de seguridad con las siguientes defensas:
- **Loopback Host Enforcement**: Rechaza cualquier petición cuyo encabezado `Host` no sea `localhost` o `127.0.0.1` (o con el puerto correspondiente) con HTTP `403 Forbidden`. Evita ataques DNS rebinding desde navegadores que intenten comunicarse con el gateway.
- **Cross-Origin Protection**: Rechaza encabezados `Origin` externos no autorizados con HTTP `403 Forbidden`. Se permite únicamente origen nulo (stdio/curl/clientes locales) o `localhost`/`127.0.0.1`.
- **Límite de Cuerpo de Solicitud**: Todo cuerpo entrante está acotado estrictamente a un máximo de 1 MiB (`1048576` bytes) para evitar agotamiento de memoria en la Raspberry Pi A+.

---

## 7. Modelo de Salud y Descubrimiento

El adaptador expone endpoints HTTP dedicados para monitoreo y orquestación:
- `GET /live`: Prueba de vida ligera (liveness probe). Responde `200 OK {"status":"alive"}`.
- `GET /ready`: Prueba de disponibilidad (readiness probe). Verifica estado interno y compatibilidad con el bridge.
- `GET /health`: Estado consolidado del sistema sin secretos (versión, estado del adapter, salud del núcleo, configuración).
- `GET /server/discover`: Información de descubrimiento de capacidades MCP y catálogo de endpoints.
- `POST /mcp`: Endpoint de transporte Streamable HTTP (stateless, chunked SSE).
