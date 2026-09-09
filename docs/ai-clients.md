# Local AI Clients Architecture & Integration

## 1. Visión General

El Gateway MCP-Pi implementa soporte nativo para **Clientes de Inteligencia Artificial Locales** (e.g. Gemini CLI, Claude Desktop, Cursor, etc.) sin exponer puertos de red a la LAN ni a Internet.

La comunicación se realiza mediante el transporte estándar **MCP Stdio** transmitido a través de túneles SSH autenticados con claves públicas/privadas dedicadas.

```text
+------------------------+
|    AI Client Local     |  (Gemini CLI / Claude Desktop en Windows)
|    (stdio transport)   |
+------------------------+
           |
           | SSH Stdio (Clave Ed25519 dedicada)
           v
+------------------------+
|    sshd en MCP-Pi      |  (Puerto 22, LAN interna)
|   (forced-command)     |
+------------------------+
           |
           | Invoca /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-client-stdio <client_id>
           v
+------------------------+
|  mcp_gateway.stdio_server
|  - MCP JSON-RPC Engine |
|  - SQLite Grants Check |
|  - Dynamic tools/list  |
|  - Guarded tools/call  |
+------------------------+
```

---

## 2. Modelo de Autenticación e Identidad Inmutable

Cada cliente cuenta con:
1. **Identidad Registrada (`ai_clients`)**:
   - `client_id`: Identificador canónico (e.g. `gemini-main`, `claude-desktop`).
   - `name`: Nombre descriptivo.
   - `enabled`: Booleano para activación/suspensión inmediata.
2. **Par de Claves Ed25519 Dedicado**:
   - Clave privada en el host del cliente (`~/.ssh/mcp_gemini_ed25519`).
   - Clave pública en MCP-Pi en `/home/mcp-gateway/.ssh/authorized_keys`.
3. **Forced Command Binding**:
   En el archivo `authorized_keys` de la cuenta `mcp-gateway`, cada clave está estrictamente prefijada:
   ```text
   command="/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-client-stdio <client_id>",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 ...
   ```

### Garantías de Seguridad del Wrapper
- **Descarte de Comandos Arbitrarios**: La variable `SSH_ORIGINAL_COMMAND` se anula inmediatamente; el cliente no puede solicitar un shell bash ni ejecutar comandos arbitrarios en la Raspberry Pi.
- **Prevención de Suplantación**: El `client_id` es inyectado por la configuración de la clave en el servidor, no por el cliente. Un cliente con la clave de `claude-desktop` jamás puede asumir la identidad de `gemini-main`.
- **Mínimo Privilegio**: Todo el proceso corre bajo la cuenta de servicio `mcp-gateway` (UID 1001, sin sudo).

---

## 3. Catálogo Dinámico y Doble Autorización

El servidor MCP stdio asegura que `tools/list` y `tools/call` compartan la misma política:
- **`tools/list`**: Evalúa en tiempo real `get_tools_catalog(client_id)`. Si el cliente no tiene permiso para una herramienta (por ejemplo, `write_file`), la herramienta ni siquiera aparece en el listado devuelto al modelo LLM.
- **`tools/call`**: Si el cliente intenta invocar una herramienta forzando la llamada RPC, el motor de políticas rechaza la ejecución con código de error y detiene la acción antes de alcanzar los targets.
