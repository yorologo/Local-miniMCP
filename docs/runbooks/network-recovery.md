# Runbook: Recuperación de Red y Estabilidad Wi-Fi (Network Recovery)

Este runbook detalla las directrices de diagnóstico, mitigación y recuperación ante interrupciones de conectividad inalámbrica en el gateway MCP-Pi equipado con el adaptador USB Realtek RTL8188EUS (`0bda:8179`).

---

## 1. Perfil del Hardware Inalámbrico y Limitaciones Físicas

- **Dispositivo USB**: `Bus 001 Device 002: ID 0bda:8179 Realtek Semiconductor Corp. RTL8188EUS 802.11n Wireless Network Adapter`
- **Módulo del Kernel**: `rtl8xxxu` (driver in-tree nativo en Debian 13 Trixie; `r8188eu` en Bullseye)
- **Dirección MAC Inmutable**: `8c:90:2d:ac:e5:c0`
- **Topología de Bus**: La Raspberry Pi Model A+ cuenta con un único canal USB 2.0 compartido directamente por el SoC BCM2835. Cargas excesivas de I/O de red concurrentes con ráfagas no limitadas pueden provocar interrupciones en el bus USB.
- **Regla Operativa de Transferencia**: Toda transferencia de archivos por SSH/SCP hacia MCP-Pi debe moderarse (e.g. `scp -l 600`) para evitar desbordes de búfer en el controlador Realtek.

---

## 2. Comportamiento ante Pérdida Temporal de Conexión Wi-Fi

Cuando el punto de acceso local se reinicia o se produce una caída temporal de la señal Wi-Fi:
1. El demonio de red (`wpa_supplicant`) entra en estado de escaneo continuo.
2. Al reaparecer el SSID, el adaptador se re-autentica automáticamente mediante WPA2.
3. El cliente DHCP renueva el lease existente para la MAC `8c:90:2d:ac:e5:c0` obteniendo la IP fija `192.168.68.85`.
4. **Resiliencia de Servicios**: Los servicios locales `mcp-gateway-admin` (Flask en `127.0.0.1:8080`) y `mcp-gateway-mcp` (Go adapter en `127.0.0.1:8090`) permanecen activos y no sufren reinicio ni degradación, pues escuchan estrictamente en la interfaz de loopback `lo`.
5. Al restablecerse la red Wi-Fi, los clientes AI pueden volver a abrir túneles SSH stdio de inmediato sin necesidad de reiniciar la Raspberry Pi.

---

## 3. Diagnóstico de Incidencias de Red

### Comprobación de Enlace Wi-Fi
En la Pi:
```bash
# Ver estado del adaptador y calidad de señal
sudo iwconfig wlan0

# Ver estadísticas de paquetes y errores
ip -s link show wlan0
```

### Comprobación de Resolución DNS Local (Pi-hole)
El gateway utiliza el Pi-hole local (`192.168.68.54`) como resolver DNS primario:
```bash
ping -c 3 192.168.68.54
nslookup google.com 192.168.68.54
```
> [!CAUTION]
> **REGLA ABSOLUTA DE SEGURIDAD**: La Raspberry Pi-hole (`192.168.68.54`) es infraestructura de red crítica preexistente. No ejecutar comandos administrativos ni intentar modificar su configuración.

---

## 4. Procedimiento de Recuperación Manual del Adaptador Wi-Fi

Si el enlace Wi-Fi se congela o el módulo del kernel entra en un estado inconsistente sin requerir reinicio completo del sistema:

### Recarga Segura del Módulo del Kernel (vía consola local o script)
```bash
# Bajar interfaz
sudo ip link set wlan0 down

# Descargar y recargar el módulo r8188eu
# En Trixie:
sudo modprobe -r rtl8xxxu && sleep 2 && sudo modprobe rtl8xxxu
# En Bullseye:
# sudo modprobe -r r8188eu && sleep 2 && sudo modprobe r8188eu

# Levantar interfaz y solicitar DHCP
sudo ip link set wlan0 up
sudo wpa_cli -i wlan0 reassociate
sudo dhcpcd -k wlan0
sudo dhcpcd -n wlan0
```

### Comprobación de Recuperación
```bash
ping -c 3 192.168.68.1     # Gateway LAN
ping -c 3 192.168.68.54    # Pi-hole
```

---

## 5. Prevención de Sobrecarga de Memoria en el Stack de Red

- **No Instalar NetworkManager**: En entornos ARMv6 con 176 MiB RAM, NetworkManager introduce una sobrecarga innecesaria de 25-35 MiB de RSS en segundo plano.
- **Mantener Configuración Mínima**: Se utiliza el stack nativo ligero (`wpa_supplicant` + `dhcpcd` o `systemd-networkd`) consumiendo menos de 4 MiB de memoria.
