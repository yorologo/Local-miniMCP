# Runbook: Canal SSH Seguro Raspberry Pi (MCP-Pi) → Estación de Trabajo (PC)

Este documento detalla la arquitectura técnica, configuración y procedimientos operativos del canal SSH unidireccional establecido entre el Gateway MCP en la Raspberry Pi y el host de cómputo local.

---

## 1. Identidades de los Nodos

### Raspberry Pi (Gateway)
- **Hostname**: `MCP-Pi`
- **Dirección IPv4**: `192.168.68.85`
- **Dirección MAC**: `8c:90:2d:ac:e5:c0`
- **Usuario de servicio**: `mcp-gateway` (UID 1001, GID 1001, sin sudo, sin login interactivo por password)
- **Ruta de clave privada**: `/home/mcp-gateway/.ssh/mcp_gateway_ed25519` (permisos 600, retenida exclusivamente en MCP-Pi)
- **Huella de clave pública (Ed25519)**: `SHA256:Vd61kRdCrV+JbNYnPyKPLVEQBi7xsQ24Dbug+epdMEY mcp-gateway@MCP-Pi`

### Estación de Trabajo / PC (Worker)
- **Hostname**: `localhost`
- **Sistema Operativo**: `Linux (Android 16 / Termux aarch64)`
- **Dirección IPv4 LAN**: `192.168.68.84`
- **Dirección MAC LAN**: `22:b6:b2:e3:73:65`
- **Interfaz LAN activa**: `wlan0`
- **Servidor SSH**: OpenSSH Server en puerto `8022` (puerto estándar sin privilegios root en entorno sandbox)
- **Identidad en el servidor**: `u0_a435` (cuenta de app no root, contexto `u:r:untrusted_app_27`, sin sudo, sin su)
- **Huella del Host (Host Fingerprint)**: `256 SHA256:qILA9dmqZNJS7PaxqDtC7weR4NdcGhruxsUYHpPish0 (ED25519)`

---

## 2. Configuración SSH y Alias `pc-local`

En `MCP-Pi`, el archivo `/home/mcp-gateway/.ssh/config` (permisos 600) define el alias:

```sshconfig
Host termux-local pc-local
    HostName 192.168.68.72
    Port 8022
    User u0_a435
    IdentityFile ~/.ssh/mcp_gateway_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking yes
    ConnectTimeout 10
```

El archivo `/home/mcp-gateway/.ssh/known_hosts` fija la clave del host para mitigar ataques de intermediario (MITM):
```text
[192.168.68.84]:8022 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIO558VBc3DlRhK/vRg5CPZV4kTD0DaY5GXoEEvjyCLmR
```

---

## 3. Delimitación de Workspace y Pruebas Negativas

### Workspace Permitido
- **Ruta raíz**: `/data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-workspace-smoke/`
- **Archivo de comprobación**: `hello.txt`
- **Contenido esperado**: `MCP PI SSH CHANNEL OK`
- **Permisos verificados**: Lectura y escritura comprobadas exitosamente sin contraseñas.

### Pruebas Negativas y Límites de Aislamiento
- **Acceso Root/Admin**: **DENEGADO**. La cuenta de destino no posee privilegios de administrador, no existe comando `sudo` funcional y el comando `su` no está instalado en el dispositivo.
- **Rutas de sistema Android**: Rutas como `/data/system` y `/data/data` devuelven estrictamente `Permission denied` por la protección del kernel y SELinux.
- **Limitación documentada (Aislamiento interno Termux)**: Por la naturaleza monousuario de la aplicación Termux en Android, la sesión SSH de `u0_a435` tiene visibilidad de lectura hacia los demás directorios del usuario en `/data/data/com.termux/files/home/`. Los secretos locales (como `.mcp-pi.local.env`) deben mantenerse con permisos restrictivos `600` y fuera de los directorios de trabajo compartidos.

---

## 4. Política de Red y Firewall

- **Tráfico SSH**: Confinado exclusivamente a la subred local (`192.168.68.0/22`).
- **Restricción**: En entornos Android no rooteados las reglas de `iptables` están bajo control del sistema operativo móvil. Se recomienda enrutamiento cerrado a nivel de router Wi-Fi y aislamiento de clientes si se requiere mayor compartimentación.

---

## 5. Procedimiento de Revocación de Emergencia

Para cortar de forma inmediata el acceso desde la Raspberry Pi hacia el PC:

1. **Opción 1: Revocación de Clave en el PC (Inmediata)**
   Editar `~/.ssh/authorized_keys` en el host destino y eliminar o comentar la línea correspondiente a `mcp-gateway@MCP-Pi`:
   ```bash
   sed -i '/mcp-gateway@MCP-Pi/d' ~/.ssh/authorized_keys
   ```
   *Efecto*: Todo intento de conexión futuro desde `MCP-Pi` es rechazado con `Permission denied (publickey)`.

2. **Opción 2: Detención del Servicio SSH en el PC**
   Detener el proceso del servidor SSH:
   ```bash
   pkill sshd
   ```
