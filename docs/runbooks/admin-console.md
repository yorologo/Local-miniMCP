# Runbook: Operación de la Consola de Administración

Este runbook detalla los procedimientos paso a paso para acceder, operar y solucionar problemas en la Consola Web de Administración de MCP Gateway.

---

## 1. Conexión Mediante Túnel SSH

Dado que la consola escucha exclusivamente en `127.0.0.1:8080` en la Raspberry Pi, el acceso desde su estación de trabajo requiere un túnel SSH.

### Comando de Conexión
Desde su terminal local (PC o entorno de administración):

```bash
ssh -N -L 8080:127.0.0.1:8080 Yorologo@192.168.68.85
```

> [!TIP]
> Si el puerto 8080 ya está ocupado en su máquina local, puede redirigir a un puerto alternativo como 18080:
> ```bash
> ssh -N -L 18080:127.0.0.1:8080 Yorologo@192.168.68.85
> ```
> y luego acceder a `http://127.0.0.1:18080`.

---

## 2. Gestión de Credenciales de Administrador

Las contraseñas de administración se gestionan mediante la herramienta de línea de comandos `mcp_gateway.admin_cli` ejecutada bajo el usuario de servicio `mcp-gateway`.

### 2.1 Crear o Actualizar Contraseña de Administrador
Para establecer o cambiar la contraseña del usuario `admin`:

```bash
ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.admin_cli set-password admin"
```

El comando solicitará la contraseña interactivamente de forma oculta y almacenará su hash PBKDF2 en la base de datos SQLite.

---

## 3. Control del Servicio del Sistema (`systemd`)

La consola corre como servicio administrado por systemd bajo el nombre `mcp-gateway-admin.service`.

### 3.1 Comprobar Estado del Servicio
```bash
ssh Yorologo@192.168.68.85 "systemctl status mcp-gateway-admin"
```

Debe mostrarse en estado `active (running)`.

### 3.2 Reiniciar el Servicio
```bash
ssh Yorologo@192.168.68.85 "sudo systemctl restart mcp-gateway-admin"
```

### 3.3 Detener el Servicio
```bash
ssh Yorologo@192.168.68.85 "sudo systemctl stop mcp-gateway-admin"
```

### 3.4 Ver Logs de Ejecución en Tiempo Real
```bash
ssh Yorologo@192.168.68.85 "journalctl -u mcp-gateway-admin -f -n 50"
```

---

## 4. Procedimientos de Operación Web

### 4.1 Iniciar Sesión
1. Abra su navegador web en `http://127.0.0.1:8080/login`.
2. Ingrese el nombre de usuario (`admin`) y su contraseña.
3. Tras la autenticación, será redirigido al Dashboard principal.

### 4.2 Probar un Target en Vivo
1. Diríjase a la sección **Targets** en el menú de navegación lateral.
2. En la fila del target deseado (por ejemplo, `termux-main`), haga clic en el botón **Test**.
3. El Gateway ejecutará un chequeo de estado (`target_status`) comprobando latencia y nombre del host remoto mediante el canal seguro SSH.

### 4.3 Deshabilitar un Target Temporalmente
1. En la lista de **Targets**, haga clic en el botón **Disable** (o **Enable** si ya está deshabilitado).
2. De inmediato, cualquier herramienta MCP dirigida a este target devolverá el error `TARGET_DISABLED`.

### 4.4 Activar el Kill Switch de Emergencia
Si detecta anomalías o desea cortar de forma inmediata toda interacción de los agentes de IA con los targets:
1. Acceda a la sección **Settings** en el menú lateral.
2. Localice la tarjeta destacada **Emergency Kill Switch**.
3. Haga clic en el botón rojo **Suspend All Gateway Operations**.
4. Verifique en el banner superior que el estado cambia a `GATEWAY DISABLED (KILL SWITCH ACTIVE)`.
5. En este estado, los modelos LLM reciben el error `GATEWAY_DISABLED` al intentar invocar herramientas en los targets, mientras que la consola de administración permanece accesible para diagnósticos.
6. Para restaurar el servicio, haga clic en **Enable Gateway Operations**.

---

## 5. Solución de Problemas (Troubleshooting)

### Error: "Conexión rechazada" al intentar navegar a 127.0.0.1:8080
- Verifique que el túnel SSH esté abierto y sin errores en su terminal local.
- Verifique que el servicio esté ejecutándose en la Raspberry Pi:
  `ssh Yorologo@192.168.68.85 "sudo ss -tulpn | grep 8080"`
  Debe mostrar que `python3` está escuchando en `127.0.0.1:8080`.

### Error: "Too many failed attempts. Please wait 60 seconds."
- Si se ingresan 5 contraseñas erróneas en menos de 5 minutos, el mecanismo de protección bloquea el usuario durante 60 segundos.
- Espere 60 segundos antes de intentar nuevamente o reinicie el servicio para restablecer la memoria del rate limiter si es urgente.

### Error: "CSRF token missing or invalid"
- Este error se produce si se envía un formulario con una sesión expirada.
- Refresque la página o vuelva a iniciar sesión en `http://127.0.0.1:8080/login`.
