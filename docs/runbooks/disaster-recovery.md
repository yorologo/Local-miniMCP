# Runbook: Recuperación ante Desastres (Disaster Recovery)

Este runbook detalla el procedimiento completo para reconstruir el Gateway MCP-Pi desde cero ante la pérdida total de la tarjeta microSD o reemplazo de hardware de la Raspberry Pi Model A+, utilizando únicamente el repositorio Git y la bóveda de respaldos fuera de Git (`~/.mcp_migration_backup/`).

---

## 1. Escenario de Desastre

- Fallo catastrófico o corrupción irreparable de almacenamiento físico.
- Tarjeta microSD dañada o hardware de Raspberry Pi reemplazado.
- Reconstrucción limpia requerida con retención inmutable de identidades criptográficas, configuración y base de datos.

---

## 2. Componentes Requeridos para la Reconstrucción

1. **Nueva tarjeta microSD** (mínimo 8 GB, clase 10 / UHS-I).
2. **Repositorio Git de Código**: Contiene el código fuente en Python, adaptador Go compilado para ARMv6, manifiesto, suma de comprobación y script de instalación idempotente `install.sh`.
3. **Bóveda de Respaldo Local** (`~/.mcp_migration_backup/` en la estación de trabajo):
   - `gateway.db`: Base de datos SQLite (esquema v1) con targets, proyectos, clientes, grants y settings.
   - `ssh_host_ed25519_key` y `.pub`: Clave privada y pública de host de la Raspberry Pi (`SHA256:wovttruok3M1sdIkGHUs6pMbwKvTYylrh+Maz4Iv84E`).
   - `mcp_gateway_ed25519` y `.pub`: Clave privada y pública Ed25519 de la cuenta de servicio `mcp-gateway` para conexión al Target Worker.
   - `authorized_keys`: Lista de claves públicas de clientes locales (`gemini-main`, `claude-desktop`) con directiva `forced-command`.
   - `config`: Configuración SSH con los alias de conexión hacia targets (`pc-local`, `termux-local`).
   - `export_pre_migration.json`: Exportación JSON sanitizada de respaldo adicional.

---

## 3. Procedimiento de Recuperación Paso a Paso

### Fase 1: Grabación y Configuración Inicial del Sistema Operativo
1. Descargar la imagen oficial:
   - Primaria: `Raspberry Pi OS Lite 32-bit (Debian 13 Trixie)`
   - URL: `https://downloads.raspberrypi.com/raspios_lite_armhf/images/raspios_lite_armhf-2026-06-19/2026-06-18-raspios-trixie-armhf-lite.img.xz`
2. Grabar con Raspberry Pi Imager configurando:
   - Hostname: `MCP-Pi`
   - Usuario: `Yorologo`
   - Wi-Fi SSID y contraseña de la red local
   - Habilitar SSH con autenticación por clave pública (`~/.ssh/id_ed25519.pub`)
3. Insertar la tarjeta en la Raspberry Pi y conectar a la alimentación.
4. Confirmar que el router asigne la IP `192.168.68.85`.

### Fase 2: Restauración de la Clave de Host SSH
Para que los clientes AI existentes (Gemini, Claude, Cursor) no rechacen la conexión por discrepancia de fingerprint:
```bash
# Copiar las claves de host originales a /tmp
scp ~/.mcp_migration_backup/ssh_host_ed25519_key* Yorologo@192.168.68.85:/tmp/

# En la Pi: mover a /etc/ssh y reiniciar sshd
ssh Yorologo@192.168.68.85 << 'EOF'
sudo cp /tmp/ssh_host_ed25519_key* /etc/ssh/
sudo chown root:root /etc/ssh/ssh_host_ed25519_key*
sudo chmod 600 /etc/ssh/ssh_host_ed25519_key
sudo chmod 644 /etc/ssh/ssh_host_ed25519_key.pub
sudo rm -f /tmp/ssh_host_ed25519_key*
sudo systemctl restart ssh
EOF
```
Verificar que la conexión estricta responda sin advertencias:
```bash
ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/mcp_known_hosts Yorologo@192.168.68.85 "hostname"
```

### Fase 3: Despliegue del Software Base e Instalación Idempotente
Desde la estación de trabajo:
```bash
# Crear paquete de despliegue desde git
tar --exclude='*__pycache__*' --exclude='*.pyc' -czf /tmp/mcp_deploy.tar.gz src tests bin/mcp-gateway-client-stdio bin/mcp-gateway SHA256SUMS manifest.json compatibility.json install.sh

# Transferir y extraer en la Pi
scp /tmp/mcp_deploy.tar.gz Yorologo@192.168.68.85:/tmp/
ssh Yorologo@192.168.68.85 << 'EOF'
sudo mkdir -p /home/mcp-gateway/mcp-gateway
sudo tar -xzf /tmp/mcp_deploy.tar.gz -C /home/mcp-gateway/mcp-gateway
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/mcp-gateway
cd /home/mcp-gateway/mcp-gateway
sudo ./install.sh
EOF
```

### Fase 4: Restauración del Estado y Datos Persistentes
Desde la estación de trabajo:
```bash
# Subir base de datos y credenciales de servicio
scp ~/.mcp_migration_backup/gateway.db Yorologo@192.168.68.85:/tmp/
scp ~/.mcp_migration_backup/mcp_gateway_ed25519* Yorologo@192.168.68.85:/tmp/
scp ~/.mcp_migration_backup/authorized_keys Yorologo@192.168.68.85:/tmp/
scp ~/.mcp_migration_backup/config Yorologo@192.168.68.85:/tmp/

# Restaurar en sus rutas protegidas bajo mcp-gateway
ssh Yorologo@192.168.68.85 << 'EOF'
sudo mkdir -p /home/mcp-gateway/.local/share/mcp-gateway /home/mcp-gateway/.ssh
sudo cp /tmp/gateway.db /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
sudo cp /tmp/mcp_gateway_ed25519* /home/mcp-gateway/.ssh/
sudo cp /tmp/authorized_keys /home/mcp-gateway/.ssh/
sudo cp /tmp/config /home/mcp-gateway/.ssh/
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/.local/share/mcp-gateway /home/mcp-gateway/.ssh
sudo chmod 700 /home/mcp-gateway/.local/share/mcp-gateway /home/mcp-gateway/.ssh
sudo chmod 600 /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
sudo chmod 600 /home/mcp-gateway/.ssh/mcp_gateway_ed25519
sudo chmod 644 /home/mcp-gateway/.ssh/mcp_gateway_ed25519.pub
sudo chmod 600 /home/mcp-gateway/.ssh/authorized_keys
sudo chmod 600 /home/mcp-gateway/.ssh/config
sudo rm -f /tmp/gateway.db /tmp/mcp_gateway_ed25519* /tmp/authorized_keys /tmp/config /tmp/mcp_deploy.tar.gz

# Reiniciar servicios
sudo systemctl restart mcp-gateway-admin mcp-gateway-mcp
EOF
```

### Fase 5: Validación y Cierre
1. **Ejecutar Doctor**:
   ```bash
   ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway doctor"
   ```
   **Resultado requerido**: `HEALTHY`.
2. **Ejecutar Suite E2E de Clientes**:
   ```bash
   python scripts/verify_phase_6a.py
   ```
   **Resultado requerido**: 4/4 bloques aprobados.
