# Runbook: MCP Gateway Safe Uninstallation

Este runbook detalla los pasos para desinstalar el MCP Gateway de forma ordenada, preservando o purgando los datos según sea requerido.

---

## 1. Desinstalación Estándar (Preserva Datos)

Detiene los servicios, elimina las unidades de systemd y retira el binario ejecutable, manteniendo intacta la base de datos y respaldos en `.local/share/mcp-gateway`:

```bash
sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway uninstall
```

Salida esperada:
```text
Stopped and disabled service mcp-gateway-mcp
Stopped and disabled service mcp-gateway-admin
Removed systemd unit /etc/systemd/system/mcp-gateway-mcp.service
Removed systemd unit /etc/systemd/system/mcp-gateway-admin.service
Removed CLI executable /usr/local/bin/mcp-gateway
Preserved data directory /home/mcp-gateway/.local/share/mcp-gateway and config /home/mcp-gateway/.config/mcp-gateway
```

---

## 2. Desinstalación Completa (Purga de Datos)

Si se desea eliminar la totalidad del software y los datos almacenados:

```bash
sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway uninstall --purge
```

> [!CAUTION]
> La opción `--purge` eliminará permanentemente la base de datos `gateway.db` y todos los respaldos locales. Esta acción no se puede deshacer.
