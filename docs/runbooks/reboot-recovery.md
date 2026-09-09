# Runbook: Recuperación ante Reinicios y Pérdida de Energía (Reboot Recovery)

Este runbook describe el comportamiento esperado, las garantías de resiliencia del sistema y los pasos de verificación y resolución de incidencias tras un reinicio planificado o una pérdida abrupta de suministro eléctrico en la Raspberry Pi Model A+.

---

## 1. Comportamiento y Garantías de Resiliencia

### Integridad de la Base de Datos SQLite ante Apagón Abrupto
- **Garantía ACID**: SQLite utiliza el modo de journaling con sincronización estricta (`PRAGMA synchronous = FULL` / transacciones atómicas).
- **Recuperación Automática**: Al iniciar el servicio, el motor SQLite detecta si hubo una transacción incompleta mediante el archivo journal/WAL y efectúa el rollback de forma transparente sin intervención humana.
- **Sin Corrupción Silenciosa**: Toda mutación en `gateway.db` es precedida por validación de esquema y verificada periódicamente por `mcp-gateway doctor` (`PRAGMA integrity_check`).

### Escritura Controlada Atómica (`write_file`)
- Las escrituras en targets se efectúan mediante reemplazo atómico remoto con archivo temporal y `fsync`, garantizando que un corte de energía en el gateway o en el worker nunca deje un archivo a medio escribir ni corrompa el contenido original.

### Auto-Arranque por systemd
- Los servicios `mcp-gateway-admin.service` y `mcp-gateway-mcp.service` están configurados con:
  ```ini
  Restart=on-failure
  RestartSec=5
  After=network.target
  WantedBy=multi-user.target
  ```
- Ambos servicios inician automáticamente en cuanto la red local está activa.

---

## 2. Procedimiento de Verificación Post-Reinicio

Tras cualquier reinicio o restablecimiento de energía:

### Paso 1: Espera de Arranque (45 a 60 Segundos)
La Raspberry Pi Model A+ tarda aproximadamente 45 segundos en:
1. Cargar el kernel Linux desde la microSD.
2. Inicializar el bus USB e identificar el dongle Realtek RTL8188EUS (`0bda:8179`).
3. Cargar el módulo `r8188eu` y asociarse al SSID Wi-Fi.
4. Solicitar y recibir la concesión DHCP (`192.168.68.85`).

### Paso 2: Verificación de Conectividad de Red
Desde la estación de trabajo:
```bash
ping 192.168.68.85 -n 4
```
**Resultado esperado**: 4 paquetes transmitidos, 4 recibidos (0% de pérdida), latencia ~2-15 ms.

### Paso 3: Verificación de Servicios
```bash
ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/mcp_known_hosts Yorologo@192.168.68.85 "sudo systemctl is-active mcp-gateway-admin mcp-gateway-mcp"
```
**Resultado esperado**:
```text
active
active
```

### Paso 4: Verificación Integral con Doctor
```bash
ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway doctor"
```
**Resultado esperado**:
```text
OVERALL STATUS: HEALTHY
```
Todos los chequeos en `[PASS]`, incluyendo integridad de SQLite, catálogo de herramientas, permisos de claves y probes HTTP locales `/live` y `/ready`.

---

## 3. Guía de Diagnóstico y Resolución de Problemas

### Problema A: La Raspberry Pi no responde a Ping tras > 2 Minutos
1. **Comprobar los LEDs físicos en la Raspberry Pi Model A+**:
   - **LED Rojo (PWR)**: Debe estar encendido fijo. Si parpadea o está apagado, la fuente de alimentación no entrega 5.0V estables o el cable Micro-USB está defectuoso.
   - **LED Verde (ACT)**: Debe parpadear brevemente durante el arranque y luego apagarse o parpadear ocasionalmente.
     - *Si parpadea en un patrón rítmico (ej. 4 parpadeos = loader no encontrado, 7 parpadeos = kernel no encontrado)*: La tarjeta microSD no está bien insertada o la partición boot está dañada.
2. **Comprobar el Adaptador Wi-Fi USB**:
   - Verificar si el LED azul del dongle Realtek RTL8188EUS parpadea. Si está completamente apagado, extraerlo y reinsertarlo firmemente en el puerto USB hembra de la Pi.

### Problema B: El Hostname o la IP cambiaron
- Si el router asignó una IP diferente a `192.168.68.85`:
  - Verificar en la consola web del router la tabla DHCP para la MAC `8c:90:2d:ac:e5:c0`.
  - Asegurar que la reserva estática para `8c:90:2d:ac:e5:c0` apunte a `192.168.68.85`.

### Problema C: Uno de los Servicios está en estado `failed`
1. Consultar el log del servicio:
   ```bash
   ssh Yorologo@192.168.68.85 "sudo journalctl -u mcp-gateway-admin -n 50 --no-pager"
   ```
2. Ejecutar la auto-reparación no destructiva:
   ```bash
   ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway repair"
   ```
