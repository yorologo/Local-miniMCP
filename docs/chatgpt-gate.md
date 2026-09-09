# ChatGPT Integration Gate & Remote Ingress Policy

## 1. Contexto y Estado del Gate

- **Estado del Gate**: `BLOCKED_BY_PRODUCT_PLAN` (Fase 6A Closeout completada; integración cloud deferred a Fase 6B)
- **Veredicto**: `BLOCKED` (No avanzar a ChatGPT hasta completar diseño y aprobación de Fase 6B)
- **Invariante de Seguridad**: `NO PUBLIC EXPOSURE` (Cero puertos expuestos a LAN o Internet)
- **Servicio MCP Local**: `mcp-gateway-mcp.service` (`mcp-gateway-adapter`) escuchando estrictamente en `127.0.0.1:8090/mcp`.
- **Servicio Admin Local**: `mcp-gateway-admin.service` escuchando estrictamente en `127.0.0.1:8080`.

---

## 2. Razón Fundamental del Gate

La Raspberry Pi Model A+ cuenta con especificaciones de hardware extremadamente acotadas:
- SoC BCM2835 single-core ARMv6 a 700 MHz.
- 176 MiB de memoria RAM libre utilizable.
- Adaptador USB Wi-Fi (Realtek RTL8188EUS) sensible a ráfagas de tráfico concurrente.

Exponer directamente puertos de la Raspberry Pi a la red local o a Internet para consumo por OpenAI / ChatGPT violaría de inmediato los principios rectores del proyecto:
1. **Deny-by-default y Mínimo Privilegio**: La superficie de ataque debe mantenerse en cero exposición externa no autenticada.
2. **Protección de Red Preexistente**: La infraestructura local (incluyendo Pi-hole en `192.168.68.54`) no debe quedar expuesta a tráfico entrante no auditado ni a escaneos automatizados.
3. **Fail-Closed**: Cualquier mecanismo de túnel o proxy hacia la nube debe contar con autenticación de identidad previa a la llegada del payload a Python Gateway Core.

---

## 3. Estrategia de Dos Fases

### Fase 6A: Clientes AI Locales (Activa)
Los clientes corren dentro de la estación de trabajo local (Windows / macOS / Linux) y se conectan mediante transporte seguro `stdio` sobre SSH con identidades autenticadas por clave Ed25519 forzada (`mcp-gateway-client-stdio`):
- `gemini-main`: Gemini CLI vía stdio sobre SSH.
- `claude-desktop`: Claude Desktop vía stdio sobre SSH.
- Cero puertos de red abiertos a la LAN o a Internet.

### Fase 6B: ChatGPT & Clientes Cloud (Futura)
Para conectar ChatGPT al endpoint Streamable HTTP (`127.0.0.1:8090/mcp`), se requerirá:
1. **Túnel Criptográfico Seguro**: Cloudflare Tunnel / Tailscale con terminación TLS y políticas de acceso.
2. **Autenticación por Token / mTLS**: Mapeo estricto del token HTTP a una entrada en la tabla `ai_clients` y verificación en `grants`.
3. **Protección Perimetral Activa**:
   - `Host` header validation (restringido al FQDN autorizado).
   - `Origin` validation contra dominios permitidos.
   - Límite de carga útil estricto (1 MiB max).
   - Rate limiting a nivel de gateway para no saturar la CPU ARMv6.
4. **Emergency Kill Switch**: Capacidad de suspender instantáneamente el cliente cloud desde el Admin Console (`127.0.0.1:8080/settings`).
