# Runbook: Recuperación por Rollback Físico de MicroSD

Este runbook detalla el procedimiento para revertir la Raspberry Pi Model A+ a la tarjeta microSD original conocida y verificada (Debian 11 Bullseye) en caso de fallo, inestabilidad o incompatibilidad durante o después de la migración de sistema operativo.

---

## 1. Criterios de Activación del Rollback Físico

Activar este procedimiento inmediatamente si se presenta cualquiera de las siguientes condiciones:
- **Inestabilidad del driver Wi-Fi**: Desconexiones recurrentes del adaptador RTL8188EUS (`0bda:8179`) o fallos del módulo `r8188eu` en el nuevo kernel.
- **Bloqueo en el arranque**: La Raspberry Pi no completa el boot en la nueva tarjeta (LED ACT parpadeante con patrón de error o apagado constante).
- **Incompatibilidad ARMv6**: Fallos de segmentación o errores de compilación/ejecución de paquetes críticos en la arquitectura `armv6l`.
- **Agotamiento severo de recursos**: El nuevo SO consume excesiva RAM en reposo (ej. disponible < 25 MiB de los 176 MiB totales).
- **Fallo crítico en Doctor**: `mcp-gateway doctor` reporta errores no reparables de forma no destructiva.

---

## 2. Procedimiento de Ejecución (< 2 Minutos)

```text
+-------------------+      +-------------------+      +-------------------+
| 1. Apagar Raspberry| ---> | 2. Extraer Nueva  | ---> | 3. Reinsertar     |
| (Desconectar 5V)  |      |    MicroSD        |      |    Tarjeta Bullseye|
+-------------------+      +-------------------+      +-------------------+
                                                                |
                                                                v
+-------------------+      +-------------------+      +-------------------+
| 6. Doctor         | <--- | 5. Conectar SSH   | <--- | 4. Encender       |
| HEALTHY           |      | Yorologo@...85    |      | (Reconectar 5V)   |
+-------------------+      +-------------------+      +-------------------+
```

### Paso 1: Apagado Seguro o Desconexión
Si el sistema responde por SSH:
```bash
ssh Yorologo@192.168.68.85 "sudo shutdown -h now"
```
Esperar 15 segundos hasta que el LED verde ACT deje de parpadear por completo. Si el sistema está congelado o inaccesible, desconectar físicamente la fuente de alimentación Micro-USB de 5V.

### Paso 2: Extracción de la Nueva Tarjeta
- Presionar suavemente y extraer la tarjeta microSD de prueba de la ranura de la Raspberry Pi Model A+.
- Guardarla en un sobre antiestático o estuche protector etiquetado como "Prueba SO".

### Paso 3: Reiserción de la Tarjeta MicroSD Original (Bullseye)
- Insertar la tarjeta microSD original (etiquetada como `KNOWN_GOOD_PHYSICAL_ROLLBACK`) en la ranura hasta que quede firmemente encajada.

### Paso 4: Encendido
- Conectar la fuente de alimentación Micro-USB.
- El LED rojo de energía debe encenderse fijo y el LED verde ACT comenzará a parpadear leyendo el kernel de Bullseye.

### Paso 5: Espera de Asociación de Red (45-60 Segundos)
- La Raspberry Pi cargará automáticamente el driver `r8188eu` preexistente y se asociará a la red Wi-Fi local.
- El router le asignará la dirección IP reservada: `192.168.68.85`.

---

## 3. Verificación Post-Rollback

Desde la estación de trabajo:

1. **Comprobar Ping y Acceso SSH**:
   ```bash
   ping 192.168.68.85 -n 4
   ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/mcp_known_hosts Yorologo@192.168.68.85 "hostname -I; uname -a"
   ```
   **Resultado esperado**:
   - Host: `192.168.68.85`
   - Kernel: `Linux MCP-Pi 6.1.21+ ... armv6l`
   - Sin advertencias de host key pinning.

2. **Comprobar Estado de Servicios**:
   ```bash
   ssh Yorologo@192.168.68.85 "sudo systemctl is-active mcp-gateway-admin mcp-gateway-mcp"
   ```
   **Resultado esperado**:
   ```text
   active
   active
   ```

3. **Ejecutar Doctor de Salud**:
   ```bash
   ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway /home/mcp-gateway/mcp-gateway/bin/mcp-gateway doctor"
   ```
   **Resultado esperado**: `OVERALL STATUS: HEALTHY`.

4. **Comprobar Clientes AI**:
   ```bash
   python scripts/verify_phase_6a.py
   ```
   **Resultado esperado**: 4/4 bloques aprobados al 100%.

---

## 4. Tiempo de Recuperación Objetivo (RTO)
- **Tiempo estimado de swap físico**: 45 segundos.
- **Tiempo de arranque del SO y asociación Wi-Fi**: 45 segundos.
- **RTO total**: < 2 minutos.
- **RPO (Punto de Recuperación Objetivo)**: Cero pérdida de datos (la tarjeta Bullseye contiene el estado operacional consolidado).
