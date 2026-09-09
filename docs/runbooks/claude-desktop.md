# Runbook: Configuración y Uso de Claude Desktop con MCP-Pi Gateway

## 1. Propósito

Este runbook describe la configuración de **Claude Desktop** para conectarse de forma segura al Gateway MCP-Pi utilizando el transporte MCP Stdio encapsulado sobre SSH con la identidad de cliente `claude-desktop`.

---

## 2. Requisitos Previos

1. **Clave Privada Dedicada**:
   - En Windows: `C:\Users\<Usuario>\.ssh\mcp_claude_ed25519`
2. **Entrada en `authorized_keys` en MCP-Pi**:
   ```text
   command="/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-client-stdio claude-desktop",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 <PUBLIC_KEY> claude-desktop
   ```
3. **Registro y Grants en MCP-Pi**:
   - Cliente `claude-desktop` habilitado.
   - Grant con permiso exclusivo `read` sobre targets y proyectos.

---

## 3. Configuración en Claude Desktop

Editar el archivo de configuración de Claude Desktop en Windows:
`%APPDATA%\Claude\claude_desktop_config.json` (usualmente `C:\Users\<Usuario>\AppData\Roaming\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcp-gateway": {
      "command": "ssh",
      "args": [
        "-i", "C:/Users/esaud/.ssh/mcp_claude_ed25519",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-T",
        "mcp-gateway@192.168.68.85"
      ]
    }
  }
}
```

---

## 4. Política de Acceso y Herramientas

Para `claude-desktop`, el perfil es estrictamente de **solo lectura**:
- **Herramientas permitidas**: `health`, `list_targets`, `target_status`, `list_directory`, `file_stat`, `read_file`, `git_status`.
- **Herramientas restringidas**:
  - `run_task`: Bloqueada (requiere permiso `execute`).
  - `write_file`: Bloqueada (requiere permiso `write`).

---

## 5. Verificación de Funcionamiento

1. Iniciar la aplicación **Claude Desktop**.
2. Verificar en la esquina inferior del chat el icono de herramientas (martillo 🔨) y confirmar que aparece `mcp-gateway` con las herramientas de lectura activas.
3. Solicitar a Claude: `"Verifica el estado del gateway MCP usando la herramienta health"`.
4. Claude invocará `health` y presentará los detalles de versión y targets.
