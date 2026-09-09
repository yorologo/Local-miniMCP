# Runbook: Configuración y Uso de Gemini CLI con MCP-Pi Gateway

## 1. Propósito

Este runbook detalla los pasos para conectar un cliente **Gemini CLI** (u orquestador MCP compatible) al Gateway MCP-Pi mediante transporte stdio sobre SSH seguro, utilizando una identidad autenticada y autorizada (`gemini-main`).

---

## 2. Requisitos Previos

1. **Clave Privada SSH en el Cliente**:
   - Ubicación en Windows: `C:\Users\<Usuario>\.ssh\mcp_gemini_ed25519`
   - Permisos: Lectura exclusiva por el usuario.
2. **Clave Pública Autorizada en MCP-Pi**:
   - En `/home/mcp-gateway/.ssh/authorized_keys`:
     ```text
     command="/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-client-stdio gemini-main",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 <PUBLIC_KEY> gemini-main
     ```
3. **Registro y Grants en MCP-Pi**:
   - Cliente `gemini-main` habilitado.
   - Grant con permisos `read,execute` en targets y proyectos autorizados.

---

## 3. Configuración del Cliente

En la configuración del cliente (e.g. `gemini.config.json` o archivo de configuración de extensiones MCP):

```json
{
  "mcpServers": {
    "mcp-gateway": {
      "command": "ssh",
      "args": [
        "-i", "C:/Users/esaud/.ssh/mcp_gemini_ed25519",
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

## 4. Herramientas Disponibles para Gemini CLI

Inicialmente, `gemini-main` tiene asignado el perfil de permisos `read,execute`, lo que le permite acceder exclusivamente a las siguientes 8 herramientas:
1. `health`: Estado del gateway, versión y target count.
2. `list_targets`: Lista segura de targets configurados sin secretos.
3. `target_status`: Verificación de latencia y alcance de targets.
4. `list_directory`: Exploración de directorios en proyectos autorizados.
5. `file_stat`: Metadatos de archivos y carpetas.
6. `read_file`: Lectura segura de contenido de archivos.
7. `git_status`: Consulta del estado del repositorio git de proyectos.
8. `run_task`: Ejecución de tareas predefinidas en la lista blanca del proyecto.

> [!NOTE]
> La herramienta `write_file` **no está visible ni permitida** para `gemini-main` por defecto bajo la política deny-by-default.

---

## 5. Verificación Rápida de Conexión

Para verificar la conexión de forma interactiva desde PowerShell:

```powershell
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2026-07-28"}}' | ssh -i "$HOME/.ssh/mcp_gemini_ed25519" -o BatchMode=yes -o StrictHostKeyChecking=no -T mcp-gateway@192.168.68.85
```

Respuesta esperada:
```json
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2026-07-28", "capabilities": {"tools": {}}, "serverInfo": {"name": "mcp-gateway-adapter", "version": "0.6.0"}}}
```

---

## 6. Solución de Problemas

- **Conexión rechazada o timeout**: Verificar que la Raspberry Pi esté encendida en `192.168.68.85` y que no haya interferencia en la red Wi-Fi USB.
- **Permission denied (publickey)**: Verificar que la clave pública esté presente en `/home/mcp-gateway/.ssh/authorized_keys` con los permisos `0600`.
- **Tool not allowed**: Si una herramienta necesaria no aparece en `tools/list`, solicitar al administrador del gateway que añada el grant correspondiente en la consola web (`127.0.0.1:8080`).
