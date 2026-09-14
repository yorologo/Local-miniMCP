# Configuration Reference

Esta referencia describe únicamente configuración vigente y operativa. Los secretos locales nunca deben entrar en Git.

## Gateway Core y Registry

| Variable | Uso | Producción |
|---|---|---|
| `MCP_GATEWAY_REGISTRY` | Backend de registry (`sqlite`/`json`) | `sqlite` |
| `MCP_GATEWAY_DB` | Ruta de SQLite | `/home/mcp-gateway/.local/share/mcp-gateway/gateway.db` |
| `MCP_ADMIN_SECRET_FILE` | Secret de sesión Flask | `/home/mcp-gateway/.config/mcp-gateway/admin-secret` |

Los Targets/Projects reales viven en SQLite. `config/targets.example.json` sirve como ejemplo; `config/targets.local.json` es local y está ignorado por Git.

## Admin Console

| Variable | Uso | Producción |
|---|---|---|
| `MCP_ADMIN_HOST` | Dirección de bind IPv4 | `0.0.0.0` |
| `MCP_ADMIN_PORT` | Puerto HTTP | `80` |
| `MCP_ADMIN_ALLOWED_HOSTS` | Hosts HTTP aceptados, separados por coma | `127.0.0.1,localhost,192.168.68.55,mcp-pi` |

El código conserva `127.0.0.1` como valor por defecto para ejecuciones manuales/desarrollo seguro. La unidad systemd de producción define `MCP_ADMIN_HOST=0.0.0.0` y `MCP_ADMIN_PORT=80`, por lo que la misma consola escucha en todas las interfaces IPv4 del MCP-Pi y queda accesible tanto por `http://127.0.0.1` como por `http://192.168.68.55`.

`0.0.0.0` es únicamente la dirección de escucha; no es una URL de acceso. Los navegadores deben usar la IP real del MCP-Pi. La validación de `Host`, autenticación, CSRF y cabeceras de seguridad siguen activas. No se añade proxy, túnel ni dependencia adicional. IPv6 no se publica de forma explícita; la ruta LAN soportada y verificada es IPv4.

## Secure MCP Tunnel

El servicio `mcp-gateway-tunnel.service` lee `/home/mcp-gateway/.config/mcp-gateway/tunnel.env`.

| Variable | Uso |
|---|---|
| `CONTROL_PLANE_API_KEY` | Credencial del control plane de OpenAI |
| `CONTROL_PLANE_TUNNEL_ID` | Identidad del túnel |
| `MCP_SERVER_URL` | Backend MCP, normalmente `http://127.0.0.1:8090/mcp` |
| `MCP_EXTRA_HEADERS` | Headers de autenticación hacia el backend |
| `MCP_DISCOVERY_EXTRA_HEADERS` | Headers para discovery |
| `HEALTH_LISTEN_ADDR` | Health/metrics del tunnel client |
| `LOG_FILE` | Log del tunnel client |
| `LOG_LEVEL` | Nivel de logging |

Nunca documentar valores reales de API keys o tokens.

## Despliegue desde Termux

`.mcp-pi.local.env` es local/ignorado por Git:

```bash
MCP_PI_HOST=192.168.68.55
MCP_PI_PORT=22
MCP_PI_USER=<usuario-administrativo>
MCP_PI_PASSWORD=<secreto-local>
```

`scripts/deploy-pi.sh` usa estas variables para copiar el árbol de runtime, reiniciar unidades y ejecutar pruebas remotas.

## Settings persistidos

La consola `/settings` administra valores persistidos como:

- `gateway_enabled`: kill switch global.
- `writes_enabled`: structured filesystem writes.
- `default_timeout`.
- `max_output_bytes`.
- `max_file_read_bytes`.
- `max_write_bytes`.
- `activity_retention`.

`run_command` no depende del switch `writes_enabled`; se gobierna por grants de ejecución, Project scope y `gateway_enabled`.

### Puerto 80 y privilegios

Producción mantiene `User=mcp-gateway` y concede únicamente `CAP_NET_BIND_SERVICE` mediante systemd para enlazar TCP/80. No se ejecuta la consola como root y no se instala ningún proxy.
