# Runbook — Admin Console

## Acceso normal

En la LAN confiable:

```text
http://192.168.68.55/login
```

El servicio valida el `Host` y requiere autenticación. No se expone el endpoint MCP por LAN.

## Acceso por túnel opcional

Para una red no confiable:

```bash
ssh -N -L 18080:127.0.0.1:80 yorologo@192.168.68.55
```

Abrir `http://127.0.0.1:18080/login`.

## Estado y reinicio

```bash
ssh yorologo@192.168.68.55 "systemctl status mcp-gateway-admin --no-pager"
ssh yorologo@192.168.68.55 "sudo systemctl restart mcp-gateway-admin"
ssh yorologo@192.168.68.55 "journalctl -u mcp-gateway-admin -n 80 --no-pager"
```

## Contraseña administrativa

```bash
ssh yorologo@192.168.68.55 "sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.admin_cli set-password admin"
```

## Validación HTTP

```bash
curl -I http://192.168.68.55/login
curl -I -H 'Host: evil.example' http://192.168.68.55/login  # debe fallar 403
```

La IP `192.168.68.55` está reservada por DHCP. Si esa reserva cambia, actualizar `MCP_ADMIN_ALLOWED_HOSTS`, hacer `systemctl daemon-reload` y reiniciar el servicio; `MCP_ADMIN_HOST=0.0.0.0` no necesita cambiar.
