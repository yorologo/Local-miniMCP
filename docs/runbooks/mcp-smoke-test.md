# Runbook: Pruebas y Operación del Adaptador MCP Oficial

Este runbook detalla los procedimientos de verificación, diagnóstico, pruebas de conformidad y compilación del Adaptador Oficial MCP en MCP-Pi.

---

## 1. Comprobación del Servicio MCP (`systemd`)

El adaptador corre como servicio del sistema bajo el nombre `mcp-gateway-mcp.service`.

### 1.1 Estado del Servicio
En la Raspberry Pi (`MCP-Pi`):
```bash
systemctl status mcp-gateway-mcp
```
Debe figurar como `active (running)` bajo el usuario `mcp-gateway`.

### 1.2 Registro de Logs en Tiempo Real
```bash
journalctl -u mcp-gateway-mcp -f -n 50
```

### 1.3 Reiniciar el Servicio
```bash
sudo systemctl restart mcp-gateway-mcp
```

---

## 2. Pruebas Rápidas de Conectividad HTTP

Dado que el servicio escucha en `127.0.0.1:8090`, las pruebas se ejecutan directamente en la Raspberry o a través de un túnel SSH.

### 2.1 Chequeo de Salud (Health Probe)
```bash
curl -s http://127.0.0.1:8090/health
```
**Respuesta esperada:**
```json
{"status":"ok","adapter":"mcp-gateway-adapter","version":"0.2.0"}
```

### 2.2 Descubrimiento de Herramientas vía HTTP (Tools Discovery)
```bash
curl -s -X POST http://127.0.0.1:8090/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
**Respuesta esperada:**
Línea `data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}` listando las 8 herramientas registradas.

### 2.3 Invocación de Herramienta vía HTTP (`tools/call`)
```bash
curl -s -X POST http://127.0.0.1:8090/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"health","arguments":{}}}'
```
**Respuesta esperada:**
```text
event: message
data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"text":"{\"ok\": true, \"tool\": \"health\", ...}"}]}}
```

---

## 3. Ejecución de la Batería Completa E2E

Para ejecutar automáticamente la verificación completa (Stdio, HTTP, 8 herramientas positivas, 6 pruebas de seguridad negativas, ciclo de Kill Switch y consumo de recursos):

```bash
sudo -u mcp-gateway python3 /home/mcp-gateway/mcp-gateway/scripts/verify-phase-4c.py
```

El script reportará `ALL PHASE 4C MCP PROTOCOL VERIFICATIONS PASSED 100%!`.

---

## 4. Recompilación y Despliegue del Adaptador Go

Si se realizan cambios en el código fuente Go (`mcp-adapter/`):

### Paso 1: Cross-compilar en el Host de Desarrollo (Termux)
```bash
cd /data/data/com.termux/files/home/Projects/test/MCP_Local/mcp-adapter
CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=6 go build -ldflags="-s -w" -o mcp-gateway-adapter .
```

### Paso 2: Desplegar y Reiniciar Servicio en MCP-Pi
```bash
cd /data/data/com.termux/files/home/Projects/test/MCP_Local
bash scripts/deploy-pi.sh
```

El script transfiere el binario a `/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter`, actualiza el servicio systemd y corre las pruebas remotas.
